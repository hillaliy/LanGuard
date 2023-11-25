import React, { createContext, useEffect, useState } from 'react';
import AppNavbar from './components/AppNavbar';
import StatusBox from './components/StatusBox';
import AppRoutes from './AppRoutes';
import { fetchData } from './fetchData';
import Auth from './pages/Auth';

export const AppContext = createContext(null);

function App() {
  const [darkMode, setDarkMode] = useState(false);

  const [devices, setDevices] = useState([]);
  const [allDevices, setAllDevices] = useState(0);
  const [online, setOnline] = useState(0);
  const [offline, setOffline] = useState(0);
  const [newDevices, setNewDevices] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const [currentUser, setCurrentUser] = useState('');

  // Dark Mode
  useEffect(() => {
    const body = document.body;
    body.dataset.bsTheme = darkMode ? 'dark' : 'light';
  }, [darkMode]);

  // Fetch devices data from server

  const fetchDevices = async () => {
    try {
      const response = await fetchData('get', 'device');
      if (response) {
        setDevices(response.data);
        setAllDevices(response.counters.all_devices);
        setOnline(response.counters.online_devices);
        setOffline(response.counters.offline_devices);
        setNewDevices(response.counters.new_devices);
      }
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchDevices();
    const intervalId = setInterval(() => {
      fetchDevices();
    }, 60000);
    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedUsername = localStorage.getItem('username');

    if (storedToken && storedUsername) {
      setCurrentUser({ username: storedUsername, token: storedToken });
    }
  }, []);

  if (currentUser) {
    return (
      <AppContext.Provider
        value={{
          fetchDevices,
          darkMode,
          setDarkMode,
          devices,
          allDevices,
          online,
          offline,
          newDevices,
          searchQuery,
          setSearchQuery,
          searchTerm,
          setSearchTerm,
          currentUser,
          setCurrentUser,
        }}
      >
        <AppNavbar />
        <StatusBox />
        <AppRoutes />
      </AppContext.Provider>
    );
  }
  return (
    <AppContext.Provider
      value={{
        setCurrentUser,
      }}
    >
      <Auth />
    </AppContext.Provider>
  );
}

export default App;
