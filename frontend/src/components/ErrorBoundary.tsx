import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';


interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[RecoverAI UI Uncaught Error]:', error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex items-center justify-center p-6">
          <div className="glass-panel p-8 rounded-2xl max-w-md w-full text-center space-y-5 border border-rose-500/30">
            <div className="inline-flex p-4 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <AlertCircle className="w-10 h-10" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-bold text-slate-100">Application Rendering Error</h2>
              <p className="text-sm text-slate-400">
                {this.state.error?.message || 'An unexpected frontend or network error occurred.'}
              </p>
            </div>
            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-sm transition-all glow-cyan"
            >
              <RefreshCw className="w-4 h-4" />
              Retry Connection
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
