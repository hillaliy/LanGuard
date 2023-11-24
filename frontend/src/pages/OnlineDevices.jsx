import React, { useContext, useEffect, useState } from 'react';
import { AppContext } from '../App';
import BasePage from './BasePage';

const OnlineDevices = () => {
  const { devices } = useContext(AppContext);
  const [onlineDevices, setOnlineDevices] = useState([]);

  useEffect(() => {
    setOnlineDevices(
      devices.filter(device => device.online === true && device.known === true)
    );
  }, [devices]);

  return (
    <>
      <h3 className="text-center mt-3 text-success">Online</h3>
      <BasePage devices={onlineDevices} />
    </>
  );
};

export default OnlineDevices;
