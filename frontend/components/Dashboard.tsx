"use client";

import { useEffect, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

type Patient = { id: number; name: string; age: number; gender: string; address: string; phone: string; notes: string; };
type Visit = { id: number; patient_id: number; date: string; diagnosis: string; doctor: string; };
type Prescription = { id: number; visit_id: number; medication: string; dosage: string; };
type Billing = { id: number; patient_id: number; amount: number; status: string; date: string; };
type AuditLog = { id: number; time: string; operation: string; old_value: string; new_value: string; user: string; };

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<'patients' | 'visits' | 'prescriptions' | 'billing' | 'audit'>('patients');
  const [data, setData] = useState<any[]>([]);
  const lastMessage = useWebSocket('ws://localhost:8000/ws');

  const fetchData = async (endpoint: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/${endpoint}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    let endpoint = activeTab;
    if (activeTab === 'audit') endpoint = 'audit_log';
    fetchData(endpoint);
  }, [activeTab]);

  useEffect(() => {
    if (lastMessage) {
      console.log("WebSocket Update Received:", lastMessage);
      // Refresh current tab if relevant
      // Simple logic: just refresh whatever is open. 
      // More complex: check lastMessage.table vs activeTab
      let endpoint = activeTab;
      if (activeTab === 'audit') endpoint = 'audit_log';
      fetchData(endpoint);
    }
  }, [lastMessage, activeTab]);

  return (
    <div className="flex-1 flex flex-col h-full bg-gray-50 overflow-hidden">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-800">Medical Records</h1>
      </div>

      <div className="flex border-b border-gray-200 bg-white px-6">
        {['patients', 'visits', 'prescriptions', 'billing', 'audit'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab as any)}
            className={`px-4 py-3 text-sm font-medium capitalize ${
              activeTab === tab
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {data.length > 0 && Object.keys(data[0]).map((key) => (
                  <th key={key} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  {Object.values(row).map((val: any, i) => (
                    <td key={i} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {val}
                    </td>
                  ))}
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td className="px-6 py-4 text-center text-gray-500">No data available</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
