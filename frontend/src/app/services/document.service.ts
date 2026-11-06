
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class DocumentService {
  private http = inject(HttpClient);

  private apiUrl = 'http://127.0.0.1:8000/documents';

  uploadDocument(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post(
      `${this.apiUrl}/upload`,
      formData
    );
  }

  askQuestion(question: string, documentId: string) {
    return this.http.post<{
      answer: string;
      sources: string[];
    }>(
      `${this.apiUrl}/ask`,
      {
        question,
        document_id: documentId
      }
    );
  }
}
