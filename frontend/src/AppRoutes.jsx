import React, { useContext } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import AllDevices from './pages/AllDevices';
import NewDevices from './pages/NewDevices';
import OnlineDevices from './pages/OnlineDevices';
import OfflineDevices from './pages/OfflineDevices';
import { AppContext } from './App';
import SearchResults from './pages/SearchResults';

const AppRoutes = () => {
  const { searchTerm } = useContext(AppContext);

  return (
    <>
      {searchTerm && <Navigate to="/search" replace />}
      <Routes>
        <Route path="/" element={<AllDevices />} />
        <Route path="/online" element={<OnlineDevices />} />
        <Route path="/offline" element={<OfflineDevices />} />
        <Route path="/new-devices" element={<NewDevices />} />
        <Route
          path="/search"
          element={<SearchResults searchTerm={searchTerm} />}
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </>
  );
};

export default AppRoutes;
