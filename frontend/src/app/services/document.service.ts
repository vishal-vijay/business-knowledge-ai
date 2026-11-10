
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class DocumentService {
  private http = inject(HttpClient);

  private apiUrl = 'http://127.0.0.1:8000/documents';

  uploadDocument(file: File, businessId: string): Observable<any> {
    const formData = new FormData();

    formData.append('file', file);
    formData.append('business_id', businessId);

    return this.http.post(
      `${this.apiUrl}/upload`,
      formData
    );
  }

  askQuestion(question: string, businessId: string) {
    return this.http.post<{
      answer: string;
      sources: {
        filename: string;
        document_id: string;
      }[];
    }>(
      `${this.apiUrl}/ask`,
      {
        question,
        business_id: businessId
      }
    );
  }
}
