import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    if (import.meta.env.DEV) {
        console.error('Uncaught error:', error, errorInfo);
    }
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center text-[var(--text-primary)] bg-[var(--surface-0)] min-h-screen">
          <h2 className="text-[var(--bad)]">Oops, something went wrong.</h2>
          <button
                onClick={() => window.location.reload()}
                className="px-5 py-2.5 bg-[var(--surface-2)] border border-[var(--rule)] rounded cursor-pointer text-[var(--text-primary)] mt-4 hover:bg-[var(--rule-strong)] transition-colors"
            >
            Reload page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
