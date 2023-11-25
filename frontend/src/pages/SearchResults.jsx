import { useContext, useEffect } from 'react';
import BasePage from './BasePage';
import { AppContext } from '../App';

const SearchResults = ({ searchTerm }) => {
  const { devices, searchQuery, setSearchTerm } = useContext(AppContext);

  useEffect(() => {
    const filteredDevices = devices.filter(device => {
      const { name, ip, mac, vendor } = device;
      const searchLower = searchQuery.toLowerCase();
      return (
        name.toLowerCase().includes(searchLower) ||
        ip.toLowerCase().includes(searchLower) ||
        mac.toLowerCase().includes(searchLower) ||
        vendor.toLowerCase().includes(searchLower)
      );
    });

    setSearchTerm(filteredDevices);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devices]);

  return (
    <>
      {searchTerm && (
        <>
          <h3 className="text-center mt-3 text-success">Search results</h3>
          <BasePage devices={searchTerm} />
        </>
      )}
    </>
  );
};

export default SearchResults;
