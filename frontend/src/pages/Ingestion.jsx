import { Upload, FileText, CheckCircle, Clock, AlertCircle, Loader, Shield } from 'lucide-react';
import { jobs } from '../data/mockData';
import { cn } from '../lib/utils';

const getStatusIcon = (status) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-5 h-5 text-green-400" />;
    case 'processing':
      return <Loader className="w-5 h-5 text-primary animate-spin" />;
    case 'pending':
      return <Clock className="w-5 h-5 text-yellow-400" />;
    case 'failed':
      return <AlertCircle className="w-5 h-5 text-red-400" />;
    default:
      return null;
  }
};

const getStatusColor = (status) => {
  const colors = {
    completed: 'badge-success',
    processing: 'badge-info',
    pending: 'badge-warning',
    failed: 'badge-danger',
  };
  return colors[status] || 'badge-info';
};

export default function Ingestion() {
  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <div className="card">
        <h2 className="text-xl font-semibold text-white mb-4">Upload Feedback Data</h2>
        
        <div className="border-2 border-dashed border-dark-300 rounded-2xl p-12 text-center hover:border-primary/50 transition-all duration-300 cursor-pointer bg-dark-200/50">
          <div className="flex flex-col items-center gap-4">
            <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center">
              <Upload className="w-8 h-8 text-primary" />
            </div>
            <div>
              <p className="text-lg font-medium text-white mb-1">
                Drop CSV or JSON files here
              </p>
              <p className="text-sm text-gray-400">
                or click to browse • Max 100MB per file
              </p>
            </div>
            <button className="px-6 py-3 bg-primary hover:bg-primary/90 text-white rounded-xl font-medium transition-all duration-200">
              Select Files
            </button>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-4 bg-dark-200 rounded-xl border border-dark-300">
            <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-xs text-gray-400">Supported Formats</p>
              <p className="text-sm font-medium text-white">CSV, JSON</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3 p-4 bg-dark-200 rounded-xl border border-dark-300">
            <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-gray-400">Auto PII Detection</p>
              <p className="text-sm font-medium text-white">Enabled</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3 p-4 bg-dark-200 rounded-xl border border-dark-300">
            <div className="w-10 h-10 bg-yellow-500/10 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-yellow-400" />
            </div>
            <div>
              <p className="text-xs text-gray-400">Deduplication</p>
              <p className="text-sm font-medium text-white">Two-tier</p>
            </div>
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-white mb-1">Ingestion Jobs</h2>
            <p className="text-sm text-gray-400">Recent processing history</p>
          </div>
          <button className="text-sm text-primary hover:text-primary/80 font-medium">
            View All →
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-300">
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Job ID</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">File</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Records</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Duplicates</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Rejected</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-300">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-dark-200 transition-colors">
                  <td className="py-4 px-4">
                    <span className="text-sm font-mono text-primary">{job.id}</span>
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-gray-400" />
                      <span className="text-sm text-white">{job.file}</span>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(job.status)}
                      <span className={cn('badge', getStatusColor(job.status))}>
                        {job.status}
                      </span>
                      {job.progress && (
                        <span className="text-xs text-gray-400">({job.progress}%)</span>
                      )}
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm text-gray-300">
                      {job.records !== '—' ? job.records.toLocaleString() : '—'}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm text-yellow-400">
                      {job.duplicates || '—'}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm text-red-400">
                      {job.rejected || '—'}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm text-gray-400">{job.timestamp}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
