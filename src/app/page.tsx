import { UploadForm } from "@/components/feature/upload-form";

export default function Home() {
  return (
    <main className="flex min-h-screen w-full flex-col items-center justify-center p-4 bg-background">
      <div className="absolute inset-0 h-full w-full bg-background bg-[radial-gradient(#888_1px,transparent_1px)] [background-size:16px_16px]"></div>
      <div className="z-10 w-full max-w-2xl">
        <UploadForm />
      </div>
    </main>
  );
}
