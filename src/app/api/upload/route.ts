import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import fs from 'fs/promises';
import path from 'path';
import os from 'os';

// Function to detect available Python executable
async function detectPythonExecutable(): Promise<string> {
  const candidates = process.platform === 'win32' 
    ? ['python', 'py', 'python3'] 
    : ['python3', 'python'];

  for (const candidate of candidates) {
    try {
      const result = await new Promise<boolean>((resolve) => {
        const testProcess = spawn(candidate, ['--version'], { stdio: 'pipe' });
        testProcess.on('close', (code) => resolve(code === 0));
        testProcess.on('error', () => resolve(false));
        // Set a timeout to avoid hanging
        setTimeout(() => {
          testProcess.kill();
          resolve(false);
        }, 3000);
      });
      
      if (result) {
        return candidate;
      }
    } catch (error) {
      continue;
    }
  }
  
  throw new Error('Python executable not found. Please install Python from https://python.org or Microsoft Store');
}

export async function POST(request: NextRequest) {
  let tempFilePath: string | null = null;
  let zipFilePath: string | null = null;

  try {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    const category = formData.get('category') as string | null;
    const questionType = formData.get('questionType') as string | null;

    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }
    if (!category) {
      return NextResponse.json({ error: 'Category is required' }, { status: 400 });
    }
    if (!questionType) {
      return NextResponse.json({ error: 'Question type is required' }, { status: 400 });
    }
    
    // 1. Save uploaded file to a temporary location
    const fileBuffer = Buffer.from(await file.arrayBuffer());
    const tempDir = os.tmpdir();
    // Use original filename without timestamp for cleaner processing
    const cleanFileName = file.name.replace(/[^\w\s.-]/g, '_'); // Replace special chars
    const uniqueFileName = `${Date.now()}-${cleanFileName}`;
    tempFilePath = path.join(tempDir, uniqueFileName);
    await fs.writeFile(tempFilePath, fileBuffer);

    // Determine which Python script to run based on category and questionType
    let pythonScriptPath: string;
    
    console.log(`Processing: category=${category}, questionType=${questionType}`);
    
    if (category === 'Mock') {
      if (questionType === 'question') {
        pythonScriptPath = path.resolve('./scripts/mock_questions/wordToMD.py');
      } else if (questionType === 'solution') {
        pythonScriptPath = path.resolve('./scripts/solutions_mock/wordToMD.py');
      } else {
        return NextResponse.json({ error: 'Invalid question type for Mock' }, { status: 400 });
      }
    } else if (category === 'Section') {
      if (questionType === 'section, mcq') {
        pythonScriptPath = path.resolve('./scripts/mcq_section/wordToMD.py');
      } else if (questionType === 'passage') {
        pythonScriptPath = path.resolve('./scripts/question_passage/wordToMD.py');
      } else {
        return NextResponse.json({ error: 'Invalid question type for Section' }, { status: 400 });
      }
    } else {
      return NextResponse.json({ error: 'Invalid category' }, { status: 400 });
    }
    
    console.log(`Selected Python script: ${pythonScriptPath}`);

    // Detect the correct Python executable
    let pythonExecutable: string;
    try {
      pythonExecutable = await detectPythonExecutable();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Python not found';
      return NextResponse.json({ 
        error: `Python required: ${errorMessage}` 
      }, { status: 500 });
    }

    // Prepare arguments for the script
    // FIX: Only pass the DOCX file path as argument
    const scriptArgs = [pythonScriptPath, tempFilePath];

    const pythonProcess = spawn(pythonExecutable, scriptArgs);
    
    let scriptOutput = '';
    let scriptError = '';

    pythonProcess.stdout.on('data', (data) => {
      const chunk = data.toString();
      scriptOutput += chunk;
      console.log('[Python stdout]:', chunk);
    });

    pythonProcess.stderr.on('data', (data) => {
      const chunk = data.toString();
      scriptError += chunk;
      console.error('[Python stderr]:', chunk);
    });

    const exitCode = await new Promise<number>((resolve, reject) => {
      pythonProcess.on('close', resolve);
      pythonProcess.on('error', reject);
    });

    if (exitCode !== 0) {
      console.error('Python script error:', scriptError);
      throw new Error(`Processing failed: ${scriptError || 'Unknown error'}`);
    }
    
    // The Python script prints the path of the generated zip file to the last line of stdout
    // Extract the actual zip file path from the output, using the marker if present
    let zipFilePath: string | null = null;
    const outputLines = scriptOutput.trim().split('\n').map(l => l.trim()).filter(Boolean);
    const markerIdx = outputLines.findIndex(line => line === '===ZIP===');
    if (markerIdx !== -1 && outputLines.length > markerIdx + 1) {
      zipFilePath = outputLines[markerIdx + 1];
    } else {
      // Fallback: use last line if marker not found
      zipFilePath = outputLines[outputLines.length - 1];
    }
    // Validate that the zip file path looks correct
    if (!zipFilePath || !zipFilePath.endsWith('.zip')) {
      console.error('Invalid zip file path from Python script:', zipFilePath);
      console.error('Full Python output:', scriptOutput);
      console.error('Full Python error output:', scriptError);
      return NextResponse.json({
        error: "Processing failed to generate output file"
      }, { status: 500 });
    }
    
    // Check if the file exists before attempting to read
    try {
        await fs.access(zipFilePath);
    } catch {
        throw new Error("Processing failed to create output file");
    }

    // 3. Read the generated zip file and send it as response
    const zipBuffer = await fs.readFile(zipFilePath);
    
    // Extract the original filename from the zip file path to preserve it
    const originalZipName = path.basename(zipFilePath);
    
    const headers = new Headers();
    headers.set('Content-Type', 'application/zip');
    headers.set('Content-Disposition', `attachment; filename="${originalZipName}"`);
    headers.set('Cache-Control', 'no-cache, no-store, must-revalidate');
    headers.set('Pragma', 'no-cache');
    headers.set('Expires', '0');

    return new NextResponse(zipBuffer, {
      status: 200,
      headers,
    });

  } catch (error) {
    console.error('Upload error:', error);
    const message = error instanceof Error ? error.message : 'Processing failed';
    return NextResponse.json({ 
      error: message
    }, { status: 500 });
  } finally {
    // 4. Clean up temporary files
    if (tempFilePath) {
      try {
        await fs.unlink(tempFilePath);
      } catch (e) {
        console.error("Failed to delete temp file:", tempFilePath, e);
      }
    }
    if (zipFilePath && typeof zipFilePath === 'string') {
      try {
        if ((zipFilePath as string).endsWith('.zip')) {
          await fs.unlink(zipFilePath);
        }
      } catch (e) {
        console.error("Failed to delete zip file:", zipFilePath, e);
      }
    }
  }
}
