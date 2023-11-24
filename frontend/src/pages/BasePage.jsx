import React, { useState } from 'react';
import { Button, ButtonGroup, Dropdown, Table } from 'react-bootstrap';
import { CheckCircle, XCircle } from 'react-bootstrap-icons';
import AppPagination from '../components/AppPagination';
import DeviceModal from '../components/DeviceModal';

const BasePage = ({ devices }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [devicesPerPage, setDevicesPerPage] = useState(15);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [sortOrder, setSortOrder] = useState('asc');
  const [sortColumn, setSortColumn] = useState('ip');

  const titles = devices.length > 0 ? Object.keys(devices[0]) : [];

  // Sorting function
  const sortDevices = (a, b) => {
    if (sortColumn === 'ip') {
      // Split the IP address into octets
      const octetsA = a[sortColumn].split('.');
      const octetsB = b[sortColumn].split('.');
      // Convert each octet to a number and combine them into a single numerical value
      const numericA = octetsA.reduce(
        (acc, octet, index) => acc + parseInt(octet, 10) * 256 ** (3 - index),
        0
      );
      const numericB = octetsB.reduce(
        (acc, octet, index) => acc + parseInt(octet, 10) * 256 ** (3 - index),
        0
      );

      return sortOrder === 'asc' ? numericA - numericB : numericB - numericA;
    } else {
      const aValue = a[sortColumn].toLowerCase();
      const bValue = b[sortColumn].toLowerCase();

      return sortOrder === 'asc'
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue);
    }
  };

  // Handle column sorting
  const handleSort = columnName => {
    if (sortColumn === columnName) {
      // If clicking on the same column, toggle the sort order
      setSortOrder(prevOrder => (prevOrder === 'asc' ? 'desc' : 'asc'));
    } else {
      // If clicking on a different column, set the new column and default to ascending order
      setSortColumn(columnName);
      setSortOrder('asc');
    }
  };

  // Sorting and pagination
  function handlePageChange(newPage) {
    setCurrentPage(newPage);
  }
  // const devicesPerPage = 14;
  const sortedDevices = [...devices].sort(sortDevices);
  const startIndex = (currentPage - 1) * devicesPerPage;
  const visibleDevices = sortedDevices.slice(
    startIndex,
    startIndex + devicesPerPage
  );

  // Open device modal
  const handleOpenModal = device => {
    setSelectedDevice(device);
  };

  // Close device modal
  const handleCloseModal = () => {
    setSelectedDevice(null);
  };

  return (
    <>
      <Table striped borderless size="sm" responsive="sm" className="mx-2">
        <thead>
          <tr>
            <th>Id</th>
            <th>Icon</th>
            <th
              onClick={() => handleSort('name')}
              style={{ cursor: 'pointer' }}
            >
              Name{' '}
              {sortColumn === 'name' && (
                <span>{sortOrder === 'asc' ? '▲' : '▼'}</span>
              )}
            </th>
            <th onClick={() => handleSort('ip')} style={{ cursor: 'pointer' }}>
              Ip{' '}
              {sortColumn === 'ip' && (
                <span>{sortOrder === 'asc' ? '▲' : '▼'}</span>
              )}
            </th>
            <th>Mac address</th>
            <th
              onClick={() => handleSort('vendor')}
              style={{ cursor: 'pointer' }}
            >
              Vendor{' '}
              {sortColumn === 'vendor' && (
                <span>{sortOrder === 'asc' ? '▲' : '▼'}</span>
              )}
            </th>
            <th>Online</th>
            <th>Last seen</th>
            <th>Known</th>
          </tr>
        </thead>
        <tbody>
          {visibleDevices.map(device => (
            <tr key={device.id}>
              {titles.map(title => (
                <td key={title}>
                  {title === 'name' ? (
                    <Button
                      variant="link"
                      onClick={() => handleOpenModal(device)}
                      style={{ textDecoration: 'none' }}
                    >
                      {device.name}
                    </Button>
                  ) : title === 'lastseen' ? (
                    new Date(device[title]).toLocaleString('en-GB', {
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                      hour: 'numeric',
                      minute: 'numeric',
                    })
                  ) : title === 'icon' ? (
                    <img
                      src={`https://icons.getbootstrap.com/assets/icons/${device[title]}.svg`}
                      alt="Device Icon"
                      style={{ width: '30px', height: '30px' }}
                    />
                  ) : title === 'online' ? (
                    device[title] ? (
                      <CheckCircle color="green" size={20} />
                    ) : (
                      <XCircle color="red" size={20} />
                    )
                  ) : title === 'known' ? (
                    device[title] ? (
                      <CheckCircle color="green" size={20} />
                    ) : (
                      <XCircle color="red" size={20} />
                    )
                  ) : (
                    device[title]
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan="8" className="text-center">
              <div className="d-flex justify-content-end">
                <Dropdown as={ButtonGroup} size="sm" className="mb-auto mx-2">
                  <Button variant="light">{`Devices Per Page: ${devicesPerPage}`}</Button>
                  <Dropdown.Toggle
                    split
                    variant="light"
                    id="dropdown-split-basic"
                  />
                  <Dropdown.Menu>
                    <Dropdown.Item
                      onClick={() => {
                        setDevicesPerPage(15);
                      }}
                    >
                      15
                    </Dropdown.Item>
                    <Dropdown.Item
                      onClick={() => {
                        setDevicesPerPage(25);
                      }}
                    >
                      25
                    </Dropdown.Item>
                    <Dropdown.Item
                      onClick={() => {
                        setDevicesPerPage(50);
                      }}
                    >
                      50
                    </Dropdown.Item>
                  </Dropdown.Menu>
                </Dropdown>
                <AppPagination
                  currentPage={currentPage}
                  totalPages={Math.ceil(devices.length / devicesPerPage)}
                  onPageChange={handlePageChange}
                />
              </div>
            </td>
          </tr>
        </tfoot>
      </Table>
      <DeviceModal
        show={!!selectedDevice}
        setShow={handleCloseModal}
        device={selectedDevice}
      />
    </>
  );
};

export default BasePage;
