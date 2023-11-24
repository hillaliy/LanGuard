import React, { useContext, useEffect, useState } from 'react';
import { AppContext } from '../App';
import BasePage from './BasePage';

const NewDevices = () => {
  const { devices } = useContext(AppContext);
  const [newDevices, setNewDevices] = useState([]);

  useEffect(() => {
    setNewDevices(devices.filter(device => device.known === false));
  }, [devices]);

  return (
    <>
      <h3 className="text-center mt-3 text-danger">New Devices</h3>
      <BasePage devices={newDevices} />
    </>
  );
};

export default NewDevices;
