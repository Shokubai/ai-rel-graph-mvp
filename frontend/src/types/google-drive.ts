/**
 * Types for Google Drive API responses
 */

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime: string;
  size?: string;
  webViewLink?: string;
  thumbnailLink?: string;
  parents?: string[];
}

export interface DriveFileListResponse {
  files: DriveFile[];
  nextPageToken?: string;
  incompleteSearch?: boolean;
}

export interface DriveFileMetadata {
  id: string;
  name: string;
  mimeType: string;
  description?: string;
  starred?: boolean;
  trashed?: boolean;
  createdTime: string;
  modifiedTime: string;
  size?: string;
  owners?: Array<{
    displayName: string;
    emailAddress: string;
  }>;
}

export interface DriveFolderContents {
  folderId: string;
  files: DriveFile[];
  nextPageToken?: string;
}
