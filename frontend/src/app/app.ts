
import { Component, inject, ChangeDetectorRef, signal } from '@angular/core';
import { DocumentService } from './services/document.service';
import { marked } from 'marked';

@Component({
  selector: 'app-root',
  standalone: true,
  template: `
    <main class="container">
      <h1>Business Knowledge AI</h1>

      <!-- Document Upload -->
      <section>
        <h2>Upload Documents</h2>

        <input
          type="file"
          accept=".pdf"
          (change)="onFileSelected($event)"
        />

        <button
          [disabled]="!selectedFile || uploading"
          (click)="uploadDocument()"
        >
          {{ uploading ? 'Uploading...' : 'Upload Document' }}
        </button>

        @if (message) {
          <p>{{ message }}</p>
        }

        @if (error) {
          <p>{{ error }}</p>
        }
      </section>

      <hr />

      <!-- AI Chat -->
      <section>
        <h2>Ask Your Business Assistant</h2>

      <input
        type="text"
        placeholder="Ask something about the uploaded document..."
        [value]="question()"
        (input)="question.set($any($event.target).value)"
        (keyup.enter)="askQuestion(question())"
      />

      <button
        [disabled]="asking || !documentId || !question().trim()"
        (click)="askQuestion(question())"
      >
        {{ asking ? 'Thinking...' : 'Send' }}
      </button>

        @if (answer) {
          <div>
            <h3>AI Answer</h3>
            <div class="ai-answer" [innerHTML]="answerHtml"></div>
            <h4>Sources</h4>
            @for (source of sources; track source) {
              <p>{{ source }}</p>
            }
          </div>
        }

        @if (chatError) {
          <p>{{ chatError }}</p>
        }
      </section>
    </main>
  `
})
export class App {
  private documentService = inject(DocumentService);
  private cdr = inject(ChangeDetectorRef);

  selectedFile: File | null = null;
  uploading = false;
  message = '';
  error = '';

  asking = false;
  answer = '';
  sources: string[] = [];
  chatError = '';
  documentId: string | null = null;
  answerHtml = '';
  question = signal('');

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
    this.message = '';
    this.error = '';
  }

  uploadDocument() {
    if (!this.selectedFile) return;

    this.uploading = true;
    this.message = '';
    this.error = '';

    this.documentService
      .uploadDocument(this.selectedFile)
      .subscribe({
        next: (response) => {
          this.documentId = response.document_id;

          this.message =
            `${response.filename} uploaded successfully. ` +
            `${response.pages} pages processed.`;

          this.uploading = false;
        },
        error: (err) => {
          this.error =
            err.error?.detail || 'Document upload failed.';

          this.uploading = false;
        }
      });
  }

askQuestion(question: string) {
  if (!question.trim() || !this.documentId || this.asking) return;

  this.asking = true;
  this.question.set('');
  this.answer = '';
  this.sources = [];
  this.chatError = '';

  this.documentService
    .askQuestion(question, this.documentId)
    .subscribe({
      next: (response) => {
        this.answer = response.answer;
        this.answerHtml = marked.parse(response.answer) as string;
        this.sources = response.sources;
        this.asking = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.chatError =
          err.error?.detail || 'Unable to get an answer.';

        this.asking = false;
        this.cdr.markForCheck();
      }
    });
}
}
