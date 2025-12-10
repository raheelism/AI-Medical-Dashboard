import ChatInterface from '@/components/ChatInterface';
import Dashboard from '@/components/Dashboard';

export default function Home() {
  return (
    <main className="flex h-screen w-screen overflow-hidden bg-gray-100">
      <div className="w-1/3 min-w-[350px] max-w-[500px] h-full">
        <ChatInterface />
      </div>
      <div className="flex-1 h-full">
        <Dashboard />
      </div>
    </main>
  );
}
