import { useState } from 'react';
import Button from 'react-bootstrap/Button';
import Offcanvas from 'react-bootstrap/Offcanvas';
import ListGroup from 'react-bootstrap/ListGroup';
import { Sliders } from 'react-bootstrap-icons';

import { SERVER_ADMIN_URL } from '../config';
import packageJson from '../../package.json';

const OffCanvas = variant => {
  const [show, setShow] = useState(false);

  const handleClose = () => setShow(false);
  const handleShow = () => setShow(true);

  return (
    <>
      <Button variant={variant} onClick={handleShow} className="me-2">
        <Sliders size={20} />
      </Button>
      <Offcanvas show={show} onHide={handleClose} placement="end">
        <Offcanvas.Header closeButton>
          <Offcanvas.Title>⚙️ Settings</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body>
          <ListGroup>
            <ListGroup.Item action href={SERVER_ADMIN_URL} target="_blank">
              🔐 Admin Site
            </ListGroup.Item>
          </ListGroup>
        </Offcanvas.Body>
        <ListGroup style={{ textAlign: 'center', marginTop: '1rem' }}>
          <ListGroup.Item>📌 Version {packageJson.version}</ListGroup.Item>
          <ListGroup.Item>
            💰 Donation 🙏{' '}
            <a
              href="https://www.paypal.com/paypalme/hillaliy"
              target="_blank"
              rel="noopener noreferrer"
            >
              PayPal
            </a>
          </ListGroup.Item>
          <ListGroup.Item>
            Made with ❤️ by{' '}
            <a
              href="https://github.com/hillaliy/hillaliy"
              target="_blank"
              rel="noopener noreferrer"
            >
              @hillaliy!
            </a>
          </ListGroup.Item>
        </ListGroup>
      </Offcanvas>
    </>
  );
};

export default OffCanvas;
