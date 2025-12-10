"use client";

import { useEffect, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { Users, Calendar, Pill, CreditCard, FileText, RefreshCw, Activity, TrendingUp } from 'lucide-react';

type TabType = 'patients' | 'visits' | 'prescriptions' | 'billing' | 'audit';

const tabConfig: Record<TabType, { icon: React.ElementType; label: string; color: string; gradient: string }> = {
  patients: { icon: Users, label: 'Patients', color: 'text-blue-400', gradient: 'from-blue-500 to-indigo-600' },
  visits: { icon: Calendar, label: 'Visits', color: 'text-emerald-400', gradient: 'from-emerald-500 to-teal-600' },
  prescriptions: { icon: Pill, label: 'Prescriptions', color: 'text-purple-400', gradient: 'from-purple-500 to-pink-600' },
  billing: { icon: CreditCard, label: 'Billing', color: 'text-amber-400', gradient: 'from-amber-500 to-orange-600' },
  audit: { icon: FileText, label: 'Audit Log', color: 'text-slate-400', gradient: 'from-slate-500 to-slate-600' },
};

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('patients');
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ patients: 0, visits: 0, prescriptions: 0, pendingBills: 0 });
  const lastMessage = useWebSocket('ws://localhost:8000/ws');

  const fetchData = async (endpoint: string) => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/${endpoint}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const [patients, visits, prescriptions, billing] = await Promise.all([
        fetch('http://localhost:8000/api/patients').then(r => r.json()),
        fetch('http://localhost:8000/api/visits').then(r => r.json()),
        fetch('http://localhost:8000/api/prescriptions').then(r => r.json()),
        fetch('http://localhost:8000/api/billing').then(r => r.json()),
      ]);
      setStats({
        patients: patients.length,
        visits: visits.length,
        prescriptions: prescriptions.length,
        pendingBills: billing.filter((b: any) => b.status === 'Pending').length,
      });
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    let endpoint = activeTab === 'audit' ? 'audit_log' : activeTab;
    fetchData(endpoint);
  }, [activeTab]);

  useEffect(() => {
    if (lastMessage) {
      console.log("WebSocket Update Received:", lastMessage);
      let endpoint = activeTab === 'audit' ? 'audit_log' : activeTab;
      fetchData(endpoint);
      fetchStats();
    }
  }, [lastMessage]);

  const formatColumnHeader = (key: string) => {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const formatCellValue = (key: string, value: any) => {
    if (value === null || value === undefined) return '—';
    if (key === 'amount') return `$${Number(value).toFixed(2)}`;
    if (key === 'status') {
      const statusColors: Record<string, string> = {
        'Paid': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        'Pending': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        'Overdue': 'bg-red-500/20 text-red-400 border-red-500/30',
      };
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium border ${statusColors[value] || 'bg-slate-500/20 text-slate-400'}`}>
          {value}
        </span>
      );
    }
    if (key === 'gender') {
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${value === 'Male' ? 'bg-blue-500/20 text-blue-400' : 'bg-pink-500/20 text-pink-400'
          }`}>
          {value}
        </span>
      );
    }
    return String(value);
  };

  const StatCard = ({ icon: Icon, label, value, gradient }: { icon: React.ElementType; label: string; value: number; gradient: string }) => (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-5 hover:border-slate-600/50 transition-all">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-400 text-sm">{label}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
        </div>
        <div className={`p-3 bg-gradient-to-br ${gradient} rounded-xl shadow-lg`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col h-full bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-hidden">
      {/* Header */}
      <div className="bg-slate-800/30 backdrop-blur-sm border-b border-slate-700/50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Medical Dashboard</h1>
              <p className="text-slate-400 text-sm">Real-time patient management</p>
            </div>
          </div>
          <button
            onClick={() => {
              let endpoint = activeTab === 'audit' ? 'audit_log' : activeTab;
              fetchData(endpoint);
              fetchStats();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700/50 hover:bg-slate-600/50 border border-slate-600/50 rounded-xl text-slate-300 transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="px-6 py-4 grid grid-cols-4 gap-4">
        <StatCard icon={Users} label="Total Patients" value={stats.patients} gradient="from-blue-500 to-indigo-600" />
        <StatCard icon={Calendar} label="Total Visits" value={stats.visits} gradient="from-emerald-500 to-teal-600" />
        <StatCard icon={Pill} label="Prescriptions" value={stats.prescriptions} gradient="from-purple-500 to-pink-600" />
        <StatCard icon={TrendingUp} label="Pending Bills" value={stats.pendingBills} gradient="from-amber-500 to-orange-600" />
      </div>

      {/* Tabs */}
      <div className="px-6">
        <div className="flex gap-2 bg-slate-800/30 p-1.5 rounded-xl border border-slate-700/50 w-fit">
          {(Object.keys(tabConfig) as TabType[]).map((tab) => {
            const { icon: Icon, label, color } = tabConfig[tab];
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === tab
                    ? 'bg-slate-700/70 text-white shadow-lg'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700/30'
                  }`}
              >
                <Icon className={`w-4 h-4 ${activeTab === tab ? color : ''}`} />
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Data Table */}
      <div className="flex-1 overflow-auto p-6">
        <div className="bg-slate-800/30 backdrop-blur-sm border border-slate-700/50 rounded-2xl overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="flex items-center gap-3 text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>Loading data...</span>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700/50">
                    {data.length > 0 && Object.keys(data[0]).map((key) => (
                      <th key={key} className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider bg-slate-800/50">
                        {formatColumnHeader(key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/30">
                  {data.map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-700/20 transition-colors">
                      {Object.entries(row).map(([key, val], i) => (
                        <td key={i} className="px-6 py-4 text-sm text-slate-300 whitespace-nowrap">
                          {formatCellValue(key, val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {data.length === 0 && (
                    <tr>
                      <td colSpan={100} className="px-6 py-20 text-center text-slate-500">
                        <div className="flex flex-col items-center gap-2">
                          <FileText className="w-10 h-10 text-slate-600" />
                          <p>No data available</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
