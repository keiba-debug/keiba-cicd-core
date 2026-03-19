import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

const DOCS_DIR = path.join(process.cwd(), '..', 'docs', 'ml-experiments');

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ file: string }> }
) {
  const { file } = await params;

  // Sanitize: only allow .md files, no path traversal
  if (!file.endsWith('.md') || file.includes('..') || file.includes('/') || file.includes('\\')) {
    return NextResponse.json({ error: 'Invalid file' }, { status: 400 });
  }

  try {
    const filePath = path.join(DOCS_DIR, file);
    const content = await fs.readFile(filePath, 'utf-8');
    return NextResponse.json({ file, content });
  } catch {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
}
