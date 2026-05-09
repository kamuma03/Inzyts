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
          <h2 className="text-red-400">Oops, something went wrong.</h2>
          <button
                onClick={() => window.location.reload()}
                className="px-5 py-2.5 bg-[var(--rule-strong)] border-none rounded cursor-pointer text-white mt-4 hover:bg-[var(--accent)] transition-colors"
            >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
