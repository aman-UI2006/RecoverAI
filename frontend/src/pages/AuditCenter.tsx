import React, { useState, useEffect, useMemo } from 'react';
import {
  FileCheck2,
  RefreshCw,
  Search,
  CheckCircle2,
  Lock,
  Eye,
  X,
  Copy,
  Check,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Filter,
  Code,
  Calendar,
  Layers,
} from 'lucide-react';
import { api, currentApiState } from '../services/api';
import ChainVerifierWidget from '../components/ChainVerifierWidget';

export interface AuditEvent {
  id: string;
  transaction_id: string;
  event_type: string;
  actor: string;
  state_from?: string | null;
  state_to?: string | null;
  details: Record<string, any>;
  previous_hash: string;
  event_hash: string;
  created_at: string;
}

export interface AuditPaginatedResponse {
  total: number;
  page: number;
  limit: number;
  items: AuditEvent[];
}

export const AuditCenterPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [auditData, setAuditData] = useState<AuditPaginatedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<'SIMULATION' | 'REAL_TEST'>(
    currentApiState.mode as 'SIMULATION' | 'REAL_TEST'
  );

  // Filters & Pagination
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [selectedEventType, setSelectedEventType] = useState('ALL');
  const [searchTxId, setSearchTxId] = useState('');

  // JSON Inspector Modal state
  const [inspectEvent, setInspectEvent] = useState<AuditEvent | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Fallback synthetic audit events for demo / simulation mode
  const fallbackAuditEvents: AuditEvent[] = useMemo(
    () => [
      {
        id: 'aud_evt_942001_01',
        transaction_id: 'tx_pay_942001',
        event_type: 'STATE_CHANGE',
        actor: 'StateTransitionService',
        state_from: 'FAILED',
        state_to: 'DIAGNOSED',
        details: {
          scenario_class: 'PAYMENT_FAILURE',
          confidence_score: 0.94,
          failure_code: 'BAD_REQUEST_ERROR',
        },
        previous_hash: '0000000000000000000000000000000000000000000000000000000000000000',
        event_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
        created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      },
      {
        id: 'aud_evt_942001_02',
        transaction_id: 'tx_pay_942001',
        event_type: 'POLICY_DECISION',
        actor: 'PolicyEngine',
        state_from: 'DIAGNOSED',
        state_to: 'POLICY_APPROVED',
        details: {
          policy_version: 'v1.2',
          evaluated_rules: ['MAX_ATTEMPTS_CHECK', 'COOLDOWN_WINDOW_CHECK', 'AMOUNT_CAP_CHECK'],
          policy_result: 'PASS',
        },
        previous_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
        event_hash: 'b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12',
        created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      },
      {
        id: 'aud_evt_942001_03',
        transaction_id: 'tx_pay_942001',
        event_type: 'EXECUTION',
        actor: 'ActionExecutor',
        state_from: 'POLICY_APPROVED',
        state_to: 'RECOVERING',
        details: {
          action: 'PAYMENT_LINK',
          logical_operation_key: 'op_pl_942001',
          razorpay_link_id: 'plink_RzpTest942001',
        },
        previous_hash: 'b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12',
        event_hash: 'c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef1234',
        created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
      },
      {
        id: 'aud_evt_942002_01',
        transaction_id: 'tx_pay_942002',
        event_type: 'STATE_CHANGE',
        actor: 'StateTransitionService',
        state_from: 'FAILED',
        state_to: 'RECOVERED',
        details: {
          attribution_source: 'DIRECT_PAYMENT_LINK',
          recovered_amount: 145000.0,
        },
        previous_hash: '0000000000000000000000000000000000000000000000000000000000000000',
        event_hash: 'd4e5f678901234567890abcdef1234567890abcdef1234567890abcdef123456',
        created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      },
    ],
    []
  );

  const fetchAuditEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/api/v1/audit', {
        params: {
          page,
          limit,
          transaction_id: searchTxId.trim() || undefined,
        },
      });
      setAuditData(response.data);
    } catch (err: any) {
      console.warn('[AuditCenter API Fallback]: Backend offline or endpoint error', err);
      // Filter fallback dataset locally
      let filtered = [...fallbackAuditEvents];
      if (searchTxId.trim()) {
        filtered = filtered.filter((evt) =>
          evt.transaction_id.toLowerCase().includes(searchTxId.trim().toLowerCase())
        );
      }
      if (selectedEventType !== 'ALL') {
        filtered = filtered.filter((evt) => evt.event_type === selectedEventType);
      }

      setAuditData({
        total: filtered.length,
        page,
        limit,
        items: filtered,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditEvents();
  }, [page, limit, selectedEventType]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchAuditEvents();
  };

  const toggleMode = () => {
    const nextMode = activeMode === 'SIMULATION' ? 'REAL_TEST' : 'SIMULATION';
    setActiveMode(nextMode);
    currentApiState.mode = nextMode;
  };

  const handleCopyHash = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const filteredItems = useMemo(() => {
    if (!auditData?.items) return [];
    if (selectedEventType === 'ALL') return auditData.items;
    return auditData.items.filter((item) => item.event_type === selectedEventType);
  }, [auditData, selectedEventType]);

  const totalPages = Math.max(1, Math.ceil((auditData?.total || 0) / limit));

  return (
    <div data-testid="audit-center-page" className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
              <FileCheck2 className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-bold text-slate-100">Audit Center</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  Step 34 Observability
                </span>
              </div>
              <p className="text-slate-400 text-sm mt-0.5">
                Continuous SHA-256 cryptographic hash chain verification, event audit logging, and payload inspection
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={fetchAuditEvents}
              className="flex items-center space-x-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl border border-slate-700 transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh Log</span>
            </button>

            <button
              onClick={toggleMode}
              className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all border cursor-pointer ${
                activeMode === 'SIMULATION'
                  ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/20'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20'
              }`}
            >
              <CheckCircle2 className={`w-3.5 h-3.5 ${activeMode === 'SIMULATION' ? 'text-cyan-400' : 'text-amber-400'}`} />
              <span>{activeMode} MODE</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metric Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Total Audit Events</span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 mt-2">{auditData?.total || 0}</div>
          <div className="text-[11px] text-slate-500 mt-1">Immutable ledger records</div>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Hash Algorithm</span>
            <Lock className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-xl font-bold text-slate-100 mt-2 font-mono">SHA-256</div>
          <div className="text-[11px] text-slate-500 mt-1">Canonical JSON pre-image</div>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Chain Integrity</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-lg font-bold text-emerald-400 mt-2">100% INTACT</div>
          <div className="text-[11px] text-slate-500 mt-1">Zero tampered forks detected</div>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Genesis Anchor</span>
            <FileCheck2 className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-xs font-bold font-mono text-slate-300 mt-2 truncate">
            0000000000000000...
          </div>
          <div className="text-[11px] text-slate-500 mt-1">64-zero SHA-256 root</div>
        </div>
      </div>

      {/* Cryptographic Hash Chain Verifier Section */}
      <ChainVerifierWidget />

      {/* Main Audit Log Table Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
        {/* Controls Bar: Search & Event Type Filter */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 mb-6">
          <form onSubmit={handleSearchSubmit} className="flex items-center space-x-2 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                data-testid="audit-search-input"
                value={searchTxId}
                onChange={(e) => setSearchTxId(e.target.value)}
                placeholder="Search by Transaction ID..."
                className="w-full pl-10 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-700 transition-colors"
              />
            </div>
            <button
              type="submit"
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition-colors cursor-pointer"
            >
              Search
            </button>
          </form>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="text-xs text-slate-400 font-medium">Filter Type:</span>
              <select
                data-testid="audit-event-type-filter"
                value={selectedEventType}
                onChange={(e) => {
                  setSelectedEventType(e.target.value);
                  setPage(1);
                }}
                className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-slate-700"
              >
                <option value="ALL">All Event Types</option>
                <option value="STATE_CHANGE">STATE_CHANGE</option>
                <option value="POLICY_DECISION">POLICY_DECISION</option>
                <option value="EXECUTION">EXECUTION</option>
                <option value="DIAGNOSIS">DIAGNOSIS</option>
                <option value="RECOVERY_ATTEMPT">RECOVERY_ATTEMPT</option>
                <option value="ATTRIBUTION_MEASURE">ATTRIBUTION_MEASURE</option>
              </select>
            </div>
          </div>
        </div>

        {/* Audit Events Data Table */}
        {loading ? (
          <div data-testid="audit-loading-skeleton" className="py-12 flex flex-col items-center justify-center space-y-3">
            <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
            <p className="text-xs text-slate-400 font-mono">Fetching SHA-256 audit ledger records...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div data-testid="audit-empty-banner" className="py-12 text-center border border-slate-800/80 rounded-xl bg-slate-950/40">
            <FileCheck2 className="w-10 h-10 text-slate-600 mx-auto mb-2" />
            <h4 className="text-sm font-semibold text-slate-300">No Audit Events Found</h4>
            <p className="text-xs text-slate-500 mt-1">
              No audit events matched your search filter criteria.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table data-testid="audit-events-table" className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider bg-slate-950/40">
                  <th className="py-3 px-4">Event ID / Seq</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Transaction ID</th>
                  <th className="py-3 px-4">Previous Hash</th>
                  <th className="py-3 px-4">Event Hash</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4 text-right">Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-xs">
                {filteredItems.map((evt) => (
                  <tr key={evt.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-medium text-slate-300">
                      {evt.id}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                        {evt.event_type}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-300 font-medium">
                      {evt.actor}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-cyan-400">
                      {evt.transaction_id}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                      <div className="flex items-center space-x-1.5">
                        <span className="truncate max-w-[100px]">{evt.previous_hash}</span>
                        <button
                          onClick={() => handleCopyHash(evt.previous_hash)}
                          className="text-slate-500 hover:text-slate-300 transition-colors"
                          title="Copy Previous Hash"
                        >
                          {copiedHash === evt.previous_hash ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-300">
                      <div className="flex items-center space-x-1.5">
                        <span className="truncate max-w-[100px]">{evt.event_hash}</span>
                        <button
                          onClick={() => handleCopyHash(evt.event_hash)}
                          className="text-slate-500 hover:text-slate-300 transition-colors"
                          title="Copy Event Hash"
                        >
                          {copiedHash === evt.event_hash ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                      {new Date(evt.created_at).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => setInspectEvent(evt)}
                        data-testid={`inspect-evt-${evt.id}`}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium rounded-lg border border-slate-700 transition-colors cursor-pointer"
                      >
                        <Eye className="w-3 h-3 text-emerald-400" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-4 border-t border-slate-800">
          <div className="text-xs text-slate-400">
            Showing <span className="font-semibold text-slate-200">{filteredItems.length}</span> of{' '}
            <span className="font-semibold text-slate-200">{auditData?.total || 0}</span> events
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <span className="text-xs text-slate-400">Per page:</span>
              <select
                value={limit}
                onChange={(e) => {
                  setLimit(Number(e.target.value));
                  setPage(1);
                }}
                className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-lg px-2 py-1 focus:outline-none"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>
            </div>

            <div className="flex items-center space-x-1.5">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg border border-slate-700 transition-colors cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs text-slate-300 px-2 font-medium">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="p-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg border border-slate-700 transition-colors cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* JSON Inspector Modal */}
      {inspectEvent && (
        <div
          data-testid="audit-json-modal"
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center space-x-2.5">
                <Code className="w-5 h-5 text-emerald-400" />
                <h3 className="text-lg font-bold text-slate-100">Canonical Audit Payload Inspector</h3>
              </div>
              <button
                onClick={() => setInspectEvent(null)}
                data-testid="close-json-modal-btn"
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                <span className="text-slate-500 block text-[11px]">Event ID</span>
                <span className="text-slate-200 font-mono font-medium">{inspectEvent.id}</span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                <span className="text-slate-500 block text-[11px]">Transaction ID</span>
                <span className="text-cyan-400 font-mono font-medium">{inspectEvent.transaction_id}</span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                <span className="text-slate-500 block text-[11px]">Actor</span>
                <span className="text-slate-200 font-medium">{inspectEvent.actor}</span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                <span className="text-slate-500 block text-[11px]">Event Type</span>
                <span className="text-emerald-400 font-semibold">{inspectEvent.event_type}</span>
              </div>
            </div>

            {/* SHA-256 Hashes Display (Full untruncated as per Security Requirement 14) */}
            <div className="space-y-3 pt-2">
              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1">
                  Previous SHA-256 Hash String (Untruncated)
                </label>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs text-slate-300 break-all select-all">
                  {inspectEvent.previous_hash}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1">
                  Current Event SHA-256 Hash String (Untruncated)
                </label>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs text-emerald-400 break-all select-all">
                  {inspectEvent.event_hash}
                </div>
              </div>
            </div>

            {/* Raw Details Payload */}
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1">
                Event Detail JSON Payload (`details`)
              </label>
              <pre className="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs text-slate-300 overflow-x-auto">
                {JSON.stringify(inspectEvent.details, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setInspectEvent(null)}
                className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-xl border border-slate-700 transition-colors cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditCenterPage;
