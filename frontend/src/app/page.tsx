import { DriveFileBrowser } from "@/components/DriveFileBrowser";

export default function Home() {
  return (
    <div className="min-h-screen p-8">
      <main className="max-w-6xl mx-auto">
        <div className="border rounded-lg shadow-lg">
          <DriveFileBrowser />
        </div>
      </main>
    </div>
  );
}
