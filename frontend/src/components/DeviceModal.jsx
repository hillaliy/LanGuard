import {
  Button,
  Form,
  FormControl,
  FormGroup,
  FormLabel,
  Modal,
} from 'react-bootstrap';
import { toast } from 'react-toastify';
import { fetchData } from '../fetchData';
import { useContext, useState } from 'react';
import { AppContext } from '../App';

const DeviceModal = ({ show, setShow, device }) => {
  const { fetchDevices } = useContext(AppContext);
  const [name, setName] = useState('');
  const [icon, setIcon] = useState('');
  const [known, setKnown] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  const updateDevice = async event => {
    event.preventDefault();
    const formData = new FormData();
    if (name) {
      formData.append('name', name);
    }
    if (icon) {
      formData.append('icon', icon);
    }
    if (known) {
      formData.append('known', known);
    }

    try {
      const response = await fetchData('put', 'device/', device.id, formData);
      if (response) {
        toast.success(response.info);
        setName('');
        setIcon('');
        setShow(false);
        fetchDevices();
      }
    } catch (error) {
      toast.error(error);
    }
  };

  const deleteDevice = async () => {
    try {
      const response = await fetchData('delete', 'device/', device.id);
      if (response) {
        toast.success(response.info);
        setShowDeleteModal(false);
        setShow(false);
        fetchDevices();
      }
    } catch (error) {
      toast.error(error);
    }
  };

  return (
    <>
      {device && (
        <>
          <Modal
            size="lg"
            aria-labelledby="contained-modal-title-vcenter"
            centered
            show={show}
            onHide={() => setShow(false)}
          >
            <Modal.Header closeButton>
              <Modal.Title>{device.name}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
              <Form>
                <FormGroup className="mb-3">
                  <FormLabel>Type device name. cannot be empty</FormLabel>
                  <FormControl
                    type="text"
                    defaultValue={device.name}
                    onChange={e => {
                      setName(e.target.value);
                    }}
                  />
                </FormGroup>
                <FormGroup className="mb-3">
                  <FormLabel>
                    You can choose any icon from Bootstrap Icons -{' '}
                    <a
                      href="https://icons.getbootstrap.com"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      https://icons.getbootstrap.com
                    </a>
                    <div>
                      <small className="text-muted">
                        {' '}
                        Example: router-fill / camera-video etc...
                      </small>
                    </div>
                  </FormLabel>
                  <FormControl
                    type="text"
                    defaultValue={device.icon}
                    onChange={e => {
                      setIcon(e.target.value);
                    }}
                  />
                </FormGroup>
                <FormGroup className="mb-3">
                  <FormLabel>Select known</FormLabel>
                  <Form.Check
                    type="switch"
                    id="knownSwitch"
                    label=""
                    defaultChecked={device.known}
                    onChange={e => {
                      setKnown(e.target.checked);
                    }}
                  />
                </FormGroup>
              </Form>
            </Modal.Body>
            <Modal.Footer>
              <Button onClick={updateDevice}>Update</Button>
              <Button
                variant="danger"
                onClick={() => {
                  setShowDeleteModal(true);
                }}
              >
                Delete
              </Button>
            </Modal.Footer>
          </Modal>

          {/* Delete Modal */}
          <Modal
            size="sm"
            show={showDeleteModal}
            onHide={() => {
              setShowDeleteModal(false);
            }}
            centered
          >
            <Modal.Header closeButton>
              <Modal.Title>Confirm Delete</Modal.Title>
            </Modal.Header>
            <Modal.Body>
              Woohoo, are you sure you want to delete: {device.name}? This
              action is irreversible!
            </Modal.Body>
            <Modal.Footer>
              <Button
                variant="secondary"
                onClick={() => {
                  setShowDeleteModal(false);
                }}
              >
                Cancel
              </Button>
              <Button variant="danger" onClick={deleteDevice}>
                Delete
              </Button>
            </Modal.Footer>
          </Modal>
        </>
      )}
    </>
  );
};

export default DeviceModal;
