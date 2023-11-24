import React, { useContext, useEffect, useState } from 'react';
import BasePage from './BasePage';
import { AppContext } from '../App';

const OfflineDevices = () => {
  const { devices } = useContext(AppContext);
  const [OfflineDevices, setOfflineDevices] = useState([]);

  useEffect(() => {
    setOfflineDevices(
      devices.filter(device => device.online === false && device.known === true)
    );
  }, [devices]);

  return (
    <>
      <h3 className="text-center mt-3 text-warning">Offline</h3>
      <BasePage devices={OfflineDevices} />
    </>
  );
};

export default OfflineDevices;
