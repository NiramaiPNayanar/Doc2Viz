"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  FileQuestion,
  FileText,
  FlaskConical,
  TestTube2,
  UploadCloud,
  LoaderCircle,
  FileUp,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

type CategoryType = "Mock" | "Section";
type QuestionType = "question" | "solution" | "section, mcq" | "passage";

export function UploadForm() {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  // --- CATEGORY STATE ---
  const [category, setCategory] = React.useState<CategoryType | null>(null);
  const [questionType, setQuestionType] = React.useState<QuestionType | null>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  // --- CATEGORY BUTTONS ---
  const categories = [
    { value: 'Mock', label: 'Mock' },
    { value: 'Section', label: 'Section' },
  ];

  // --- DYNAMIC QUESTION TYPES BASED ON CATEGORY ---
  let questionTypeOptions: { value: string; label: string }[] = [];
  if (category === 'Mock') {
    questionTypeOptions = [
      { value: 'question', label: 'Question' },
      { value: 'solution', label: 'Solution' },
    ];
  } else if (category === 'Section') {
    questionTypeOptions = [
      { value: 'section, mcq', label: 'MCQ Question' },
      { value: 'passage', label: 'Passage Question' },
    ];
  }

  // --- DISABLE LOGIC ---
  const isUploadDisabled = !file || isLoading || !category || !questionType;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.name.endsWith('.docx')) {
      setFile(selectedFile);
    } else {
      setFile(null);
      toast({
        title: "Invalid file type",
        description: "Please upload a .docx file.",
        variant: "destructive",
      });
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isUploadDisabled) return;
    setIsLoading(true);
    const formData = new FormData();
    formData.append("file", file!);
    formData.append("category", category!);
    formData.append("questionType", questionType!);
    
    console.log("Submitting form with category:", category, "questionType:", questionType);  // Debug log
    
    try {
      console.log("Form data being sent:", Object.fromEntries(formData.entries()));
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        let errorMessage = `Failed to process file (${response.status})`;
        
        try {
          const contentType = response.headers.get('content-type');
          if (contentType && contentType.includes('application/json')) {
            const errorData = await response.json();
            errorMessage = errorData.error || errorMessage;
          } else {
            const errorText = await response.text();
            errorMessage = errorText || errorMessage;
          }
        } catch (parseError) {
          console.error("Error parsing response:", parseError);
        }
        
        console.error("Server error response:", errorMessage);
        throw new Error(errorMessage);
      }
      
      // Get the blob response and filename from headers
      const blob = await response.blob();
      const contentDisposition = response.headers.get('Content-Disposition');
      let fileName = 'download.zip';
      
      // Extract filename from Content-Disposition header
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
        if (filenameMatch) {
          fileName = filenameMatch[1];
        }
      }
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast({
        title: "Success!",
        description: "Your file has been processed and downloaded.",
      });
    } catch (error: any) {
      toast({
        title: "Upload Failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="w-full bg-card/80 backdrop-blur-sm border-primary/20 shadow-lg shadow-primary/10">
      <CardHeader>
        <CardTitle className="text-3xl font-bold tracking-wider font-headline text-center flex items-center justify-center gap-3">
          <UploadCloud className="text-accent" size={32} /> Word to Image
        </CardTitle>
        <CardDescription className="text-center text-muted-foreground pt-2">
          Select document type, fill in required details, and upload your .docx file to begin the conversion.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-8 pt-6">
          {/* Step 1: Category Selection */}
          <div className="space-y-4">
            <Label className="text-lg font-medium text-foreground/80">1. Select Category</Label>
            <RadioGroup
              onValueChange={(value: string) => {
                setCategory(value as CategoryType);
                setQuestionType(null);
              }}
              className="space-y-2"
              value={category || ""}
            >
              <Label htmlFor="mock" className={cn("flex items-center space-x-3 rounded-md border-2 p-4 transition-all hover:border-accent", category === 'Mock' ? 'border-accent shadow-[0_0_15px_hsl(var(--accent)/0.5)]' : 'border-input')}>
                <RadioGroupItem value="Mock" id="mock" className="peer sr-only" />
                <TestTube2 className="h-6 w-6 text-foreground/80" />
                <span className="font-medium">Mock</span>
              </Label>
              <Label htmlFor="section" className={cn("flex items-center space-x-3 rounded-md border-2 p-4 transition-all hover:border-accent", category === 'Section' ? 'border-accent shadow-[0_0_15px_hsl(var(--accent)/0.5)]' : 'border-input')}>
                <RadioGroupItem value="Section" id="section" className="peer sr-only" />
                <FlaskConical className="h-6 w-6 text-foreground/80" />
                <span className="font-medium">Section</span>
              </Label>
            </RadioGroup>
          </div>

          {/* Step 2: Question Type Selection (based on category) */}
          {category && (
            <div className="space-y-4">
              <Label className="text-lg font-medium text-foreground/80">2. Select Type</Label>
              <RadioGroup
                onValueChange={(value: string) => setQuestionType(value as QuestionType)}
                className="space-y-2"
                value={questionType || ""}
              >
                {questionTypeOptions.map((opt) => (
                  <Label
                    key={opt.value}
                    htmlFor={opt.value}
                    className={cn(
                      "flex items-center space-x-3 rounded-md border-2 p-4 transition-all hover:border-accent",
                      questionType === opt.value ? 'border-accent shadow-[0_0_15px_hsl(var(--accent)/0.5)]' : 'border-input'
                    )}
                  >
                    <RadioGroupItem value={opt.value} id={opt.value} className="peer sr-only" />
                    {opt.value === 'question' && <FileQuestion className="h-6 w-6 text-foreground/80" />}
                    {opt.value === 'solution' && <FileText className="h-6 w-6 text-foreground/80" />}
                    {opt.value === 'section, mcq' && <TestTube2 className="h-6 w-6 text-foreground/80" />}
                    {opt.value === 'passage' && <FlaskConical className="h-6 w-6 text-foreground/80" />}
                    <span className="font-medium">{opt.label}</span>
                  </Label>
                ))}
              </RadioGroup>
            </div>
          )}

          {/* Step 3: File Upload */}
          <div className="space-y-2">
            <Label className="text-lg font-medium text-foreground/80">3. Upload DOCX File</Label>
            <div className="flex items-center justify-center w-full">
              <Label htmlFor="dropzone-file" className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer bg-card/50 hover:bg-input transition-colors border-input hover:border-accent">
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                  <FileUp className="w-8 h-8 mb-4 text-muted-foreground" />
                  <p className="mb-2 text-sm text-muted-foreground">
                    <span className="font-semibold text-accent">Click to upload</span> or drag and drop
                  </p>
                  <p className="text-xs text-muted-foreground">DOCX file only</p>
                </div>
                <input ref={fileInputRef} id="dropzone-file" type="file" className="hidden" onChange={handleFileChange} accept=".docx" />
              </Label>
            </div>
            {file && (
              <div className="flex items-center justify-between rounded-md border border-input bg-input/50 p-2 mt-4 text-sm text-foreground">
                <span className="truncate">{file.name}</span>
                <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={handleRemoveFile}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </CardContent>
        <CardFooter>
          <Button
            type="submit"
            disabled={isUploadDisabled}
            className="w-full text-lg font-bold py-6 bg-primary hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed transition-all duration-300 ease-in-out transform hover:scale-105 shadow-lg shadow-primary/20 hover:shadow-accent/40 focus:shadow-accent/40 focus:ring-accent"
          >
            {isLoading ? (
              <>
                <LoaderCircle className="mr-2 h-5 w-5 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                Generate Images <UploadCloud className="ml-2 h-5 w-5" />
              </>
            )}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
