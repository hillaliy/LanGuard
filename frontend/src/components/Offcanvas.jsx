import { useState } from 'react';
import Button from 'react-bootstrap/Button';
import Offcanvas from 'react-bootstrap/Offcanvas';
import ListGroup from 'react-bootstrap/ListGroup';
import {
  Bank,
  DatabaseDown,
  DatabaseUp,
  Gear,
  GearWideConnected,
  HeartFill,
  Sliders,
} from 'react-bootstrap-icons';
import { toast } from 'react-toastify';

import { SERVER_ADMIN_URL } from '../config';
import packageJson from '../../package.json';
import { fetchData } from '../fetchData';

const OffCanvas = variant => {
  const [show, setShow] = useState(false);
  const [file, setFile] = useState(null);

  const handleClose = () => setShow(false);
  const handleShow = () => setShow(true);

  const exportDB = async () => {
    try {
      const response = await fetchData('get', 'export-db');
      if (response) {
        const blob = new Blob([JSON.stringify(response)], {
          type: 'application/json',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'lan_guard_data.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const importDB = async () => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetchData('post', 'import-db', null, formData);
      if (response) {
        toast.success(response.info);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const handleFileChange = event => {
    const selectedFile = event.target.files[0];
    setFile(selectedFile);
    importDB();
  };

  return (
    <>
      <Button variant={variant} onClick={handleShow} className="me-2">
        <Sliders size={20} />
      </Button>
      <Offcanvas show={show} onHide={handleClose} placement="end">
        <Offcanvas.Header closeButton>
          <Offcanvas.Title>
            <GearWideConnected size={30} /> Settings
          </Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <ListGroup>
            <ListGroup.Item action onClick={exportDB}>
              <DatabaseDown size={30} /> Export DB
            </ListGroup.Item>
            <ListGroup.Item>
              <label htmlFor="fileInput" style={{ cursor: 'pointer' }}>
                <DatabaseUp size={30} /> Import DB
              </label>
              <input
                type="file"
                id="fileInput"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
            </ListGroup.Item>
            <ListGroup.Item action href={SERVER_ADMIN_URL} target="_blank">
              <Gear size={30} /> Admin Site
            </ListGroup.Item>
          </ListGroup>
          <ListGroup style={{ textAlign: 'center' }}>
            <ListGroup.Item>📌 Version {packageJson.version}</ListGroup.Item>
            <ListGroup.Item
              action
              href="https://www.paypal.com/paypalme/hillaliy"
            >
              <Bank size={25} /> Donation
            </ListGroup.Item>
            <ListGroup.Item action href="https://github.com/hillaliy/hillaliy">
              Made with <HeartFill size={20} /> by @hillaliy!
            </ListGroup.Item>
          </ListGroup>
        </Offcanvas.Body>
      </Offcanvas>
    </>
  );
};

export default OffCanvas;
