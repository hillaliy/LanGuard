import React, { useContext } from 'react';
import { AppContext } from '../App';
import BasePage from './BasePage';

const AllDevices = () => {
  const { devices } = useContext(AppContext);

  return (
    <>
      <h3 className="text-center mt-3 text-primary">All Devices</h3>
      <BasePage devices={devices} />
    </>
  );
};

export default AllDevices;
