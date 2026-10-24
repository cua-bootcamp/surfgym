import { NextRequest, NextResponse } from "next/server";
import { getUserId, setUserCookie } from "@/lib/cookies";
import { fileStore } from "@/lib/file-store";
import mime from "mime-types";
import { isSessionFinalized } from "@/lib/session-lifecycle";

// GET /api/files/[filename] - Fetch a stored file for the current user
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  const userId = await getUserId(request);
  const { filename } = await params;

  let fileBuffer: Buffer | null;
  try {
    fileBuffer = await fileStore.readFile(userId, filename);
  } catch (error) {
    if (isSessionFinalized(error)) {
      const response = NextResponse.json(
        { detail: "SurfGym session finalized" },
        { status: 410 }
      );
      setUserCookie(response, userId);
      return response;
    }
    throw error;
  }

  if (!fileBuffer) {
    const errorResponse = NextResponse.json(
      { detail: "File not found" },
      { status: 404 }
    );
    setUserCookie(errorResponse, userId);
    return errorResponse;
  }

  try {
    const displayName = fileStore.getDisplayName(filename);
    const contentType = mime.lookup(displayName) || "application/octet-stream";

    const response = new NextResponse(new Uint8Array(fileBuffer), {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": `attachment; filename="${displayName}"`,
        "Content-Length": fileBuffer.length.toString(),
      },
    });

    // Set user cookie manually since we're using raw NextResponse
    setUserCookie(response, userId);

    return response;
  } catch (error) {
    console.error("File read error:", error);
    const errorResponse = NextResponse.json(
      { detail: "Failed to read file" },
      { status: 500 }
    );
    setUserCookie(errorResponse, userId);
    return errorResponse;
  }
}
