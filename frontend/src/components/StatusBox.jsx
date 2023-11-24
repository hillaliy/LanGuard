import React, { useContext } from 'react';
import { Card, Col, Container, Row } from 'react-bootstrap';
import { ExclamationTriangle, Plugin, Plus, Tv } from 'react-bootstrap-icons';
import { useNavigate } from 'react-router-dom';
import { AppContext } from '../App';

const StatusBox = () => {
  const { allDevices, online, offline, newDevices, setSearchTerm } =
    useContext(AppContext);
  const nav = useNavigate();
  return (
    <Container className="mt-4">
      <h2 class="text-center">Devices</h2>
      <Row className="justify-content-center">
        <Col xs={2}>
          <Card
            bg="primary"
            className="btn position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/');
            }}
          >
            <span class="card-icon">
              <Tv size={40} />
            </span>
            <Card.Body>
              <Card.Title>All Devices</Card.Title>
              <Card.Text>{allDevices}</Card.Text>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={2}>
          <Card
            bg="success"
            className="btn position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/online');
            }}
          >
            <span class="card-icon">
              <Plugin size={40} />
            </span>
            <Card.Body>
              <Card.Title>Online</Card.Title>
              <Card.Text>{online}</Card.Text>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={2}>
          <Card
            bg="warning"
            className="btn position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/offline');
            }}
          >
            <span class="card-icon">
              <ExclamationTriangle size={40} />
            </span>
            <Card.Body>
              <Card.Title>Offline</Card.Title>
              <Card.Text>{offline}</Card.Text>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={2}>
          <Card
            bg="danger"
            className="btn position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/new-devices');
            }}
          >
            <span class="card-icon">
              <Plus size={40} />
            </span>
            <Card.Body>
              <Card.Title>New Devices</Card.Title>
              <Card.Text>{newDevices}</Card.Text>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default StatusBox;
