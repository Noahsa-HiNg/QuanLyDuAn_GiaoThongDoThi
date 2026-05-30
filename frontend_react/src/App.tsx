import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Navbar from './components/layout/Navbar';
import { RouteGuard } from './components/layout/RouteGuard';

// Pages
import Home from './pages/Home/Home';
import Login from './pages/Login/Login';
import RouteFinder from './pages/RouteFinder/RouteFinder';
import Dashboard from './pages/Dashboard/Dashboard';
import CsgtDashboard from './pages/CsgtDashboard/CsgtDashboard';
import Incidents from './pages/Incidents/Incidents';
import AdminUsers from './pages/AdminUsers/AdminUsers';
import AdminScheduler from './pages/AdminScheduler/AdminScheduler';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="flex flex-col min-h-screen bg-gray-50">
          <Navbar />
          <main className="flex-grow">
            <Routes>
              {/* Public Routes */}
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/route-finder" element={<RouteFinder />} />
              <Route path="/dashboard" element={<Dashboard />} />

              {/* CSGT & Admin Protected Routes */}
              <Route
                path="/csgt-dashboard"
                element={
                  <RouteGuard allowedRoles={['csgt', 'admin']}>
                    <CsgtDashboard />
                  </RouteGuard>
                }
              />
              <Route
                path="/incidents"
                element={
                  <RouteGuard allowedRoles={['csgt', 'admin']}>
                    <Incidents />
                  </RouteGuard>
                }
              />

              {/* Admin-Only Protected Routes */}
              <Route
                path="/admin/users"
                element={
                  <RouteGuard allowedRoles={['admin']}>
                    <AdminUsers />
                  </RouteGuard>
                }
              />
              <Route
                path="/admin/scheduler"
                element={
                  <RouteGuard allowedRoles={['admin']}>
                    <AdminScheduler />
                  </RouteGuard>
                }
              />
            </Routes>
          </main>
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
