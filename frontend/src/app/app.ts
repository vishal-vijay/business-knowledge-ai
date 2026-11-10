
import { Component, inject, ChangeDetectorRef, signal } from '@angular/core';
import { DocumentService } from './services/document.service';
import { marked } from 'marked';
import { finalize } from 'rxjs';
import { ElementRef, ViewChild } from '@angular/core';


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
<!-- AI Chat -->
<section>
  <h2>Ask Your Business Assistant</h2>

<div class="chat-container" #chatContainer>
  @for (msg of messages; track $index) {
      <div
        class="message"
        [class.user-message]="msg.role === 'user'"
        [class.ai-message]="msg.role === 'assistant'"
      >
        <strong>
          {{ msg.role === 'user' ? 'You' : 'AI Assistant' }}
        </strong>

<div [innerHTML]="msg.html || msg.content"></div>
        @if (msg.sources?.length) {
          <div class="sources">
            <strong>Sources:</strong>
            @for (source of msg.sources; track source) {
              <p>{{ source }}</p>
            }
          </div>
        }
      </div>
    }
  </div>

  @if (asking) {
    <p>AI is thinking...</p>
  }

  <input
    type="text"
    placeholder="Ask something about the uploaded document..."
    [value]="question()"
    (input)="question.set($any($event.target).value)"
    (keyup.enter)="askQuestion(question())"
  />

  <button
    [disabled]="asking || !hasUploadedDocument || !question().trim()"
    (click)="askQuestion(question())"
  >
    {{ asking ? 'Thinking...' : 'Send' }}
  </button>

  @if (chatError) {
    <p>{{ chatError }}</p>
  }
</section>
    </main>
  `,
  styleUrl: './app.css'
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
  @ViewChild('chatContainer')
  chatContainer!: ElementRef<HTMLDivElement>;

  messages: {
    role: 'user' | 'assistant';
    content: string;
    html?: string;
    sources?: string[];
  }[] = [];

  businessId = 'demo-business-001';
  hasUploadedDocument = true;

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
      .uploadDocument(this.selectedFile, this.businessId)
      .pipe(
        finalize(() => {
          this.uploading = false;
          this.cdr.markForCheck();
        })
      )
      .subscribe({
        next: (response) => {
          this.hasUploadedDocument = true;
          this.message =
            `${response.filename} uploaded successfully. ` +
            `${response.pages} pages processed.`;

          this.uploading = false;
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.error =
            err.error?.detail || 'Document upload failed.';

          this.uploading = false;
          this.cdr.markForCheck();
        }
      });
  }

  askQuestion(question: string) {
    if (!question.trim() || this.asking) return;

    this.messages.push({
      role: 'user',
      content: question
    });

    this.cdr.detectChanges();
    this.scrollToBottom();

    this.asking = true;
    this.question.set('');
    this.chatError = '';

    this.documentService
      .askQuestion(question, this.businessId)
      .subscribe({
        next: (response) => {
          this.messages.push({
            role: 'assistant',
            content: response.answer,
            html: marked.parse(response.answer) as string,
            sources: [
              ...new Set(
                response.sources.map(
                  (source: { filename: string }) => source.filename
                )
              )
            ]
          });

          this.asking = false;
          this.cdr.markForCheck();
          this.scrollToBottom();
        },

        error: (err) => {
          this.chatError =
            err.error?.detail || 'Unable to get an answer.';

          this.asking = false;
          this.cdr.markForCheck();
        }
      });
  }

  private scrollToBottom() {
    requestAnimationFrame(() => {
      const container = this.chatContainer?.nativeElement;

      if (!container) return;

      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      });
    });
  }
}
