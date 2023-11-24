import React, { useContext } from 'react';
import { Col, Container, Row } from 'react-bootstrap';
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
          <div
            className="card btn btn-primary position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/');
            }}
          >
            <span class="card-icon">
              <Tv size={40} />
            </span>
            <div class="card-body">
              <h5 class="card-title">All Devices</h5>
              <p class="card-text">{allDevices}</p>
            </div>
          </div>
        </Col>
        <Col xs={2}>
          <div
            className="card btn btn-success position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/online');
            }}
          >
            <span class="card-icon">
              <Plugin size={40} />
            </span>
            <div class="card-body">
              <h5 class="card-title">Online</h5>
              <p class="card-text">{online}</p>
            </div>
          </div>
        </Col>
        <Col xs={2}>
          <div
            className="card btn btn-warning position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/offline');
            }}
          >
            <span class="card-icon">
              <ExclamationTriangle size={40} />
            </span>
            <div class="card-body">
              <h5 class="card-title">Offline</h5>
              <p class="card-text">{offline}</p>
            </div>
          </div>
        </Col>
        <Col xs={2}>
          <div
            className="card btn btn-danger position-relative"
            onClick={() => {
              setSearchTerm('');
              nav('/new-devices');
            }}
          >
            <span
              class="card-icon
            "
            >
              <Plus size={40} />
            </span>
            <div class="card-body">
              <h5 class="card-title">New Devices</h5>
              <p class="card-text">{newDevices}</p>
            </div>
          </div>
        </Col>
      </Row>
    </Container>
  );
};

export default StatusBox;
