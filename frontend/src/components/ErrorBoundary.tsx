"use client";

import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="flex h-full items-center justify-center p-8 text-center">
          <div className="max-w-md rounded-2xl border border-red-100 bg-white p-8 shadow-[0_10px_40px_rgba(15,23,42,0.08)]">
            <div className="mx-auto mb-4 h-14 w-14 rounded-full bg-red-50 flex items-center justify-center">
              <span className="text-[28px] font-black text-red-600">!</span>
            </div>
            <h2 className="font-news-headline text-[22px] font-black tracking-[-0.03em] text-[#071225]">
              Something went wrong
            </h2>
            <p className="mt-3 text-[15px] leading-6 text-slate-500">
              We encountered an unexpected error. The team has been notified.
            </p>
            <button
              type="button"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="mt-6 inline-flex items-center gap-2 rounded-md bg-[#071225] px-6 py-3 text-sm font-black uppercase tracking-[0.16em] text-white transition hover:bg-red-600"
            >
              Reload Page
            </button>
            {this.state.error && (
              <details className="mt-6 text-left text-xs text-slate-400">
                <summary className="cursor-pointer font-mono">Error details</summary>
                <pre className="mt-2 overflow-auto rounded bg-slate-100 p-3 font-mono text-red-700">
                  {this.state.error.toString()}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}