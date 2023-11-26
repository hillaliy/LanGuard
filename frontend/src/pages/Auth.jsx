import React, { useContext, useState } from 'react';
import Container from 'react-bootstrap/Container';
import Navbar from 'react-bootstrap/Navbar';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import { AppContext } from '../App';
import axios from 'axios';
import { SERVER_URL } from '../config';
import { toast } from 'react-toastify';
import { InputGroup } from 'react-bootstrap';
import { Key, Person } from 'react-bootstrap-icons';

const Auth = () => {
  const { setCurrentUser } = useContext(AppContext);
  const [registrationToggle, setRegistrationToggle] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');

  const submitRegistration = async e => {
    e.preventDefault();
    try {
      const response = await axios.post(`${SERVER_URL}register/`, {
        username,
        password,
        password_confirm: passwordConfirm,
      });

      toast.success(`Registration successful: ${response.data.username}`);

      setUsername('');
      setPassword('');

      submitLogin(e);
    } catch (error) {
      console.error(
        'Registration failed:',
        error.response ? error.response.data : error.message
      );
    }
  };

  const submitLogin = async e => {
    e.preventDefault();
    try {
      const response = await axios.post(`${SERVER_URL}login/`, {
        username,
        password,
      });

      setCurrentUser(response.data);
      localStorage.setItem('token', response.data.token);
      localStorage.setItem('username', response.data.username);
    } catch (error) {
      console.error(
        'Login failed:',
        error.response ? error.response.data : error.message
      );
    }
  };

  const updateFormBtn = () => {
    setRegistrationToggle(!registrationToggle);
  };

  return (
    <>
      <Navbar bg="dark" variant="dark">
        <Container>
          <Navbar.Brand>
            <img
              alt=""
              src="/logo.png"
              width="30"
              height="30"
              className="d-inline-block align-top"
            />{' '}
            LanGuard
          </Navbar.Brand>
          <Navbar.Toggle />
          <Navbar.Collapse className="justify-content-end">
            <Navbar.Text>
              <Button id="form_btn" onClick={updateFormBtn} variant="light">
                {registrationToggle ? 'Register' : 'Login'}
              </Button>
            </Navbar.Text>
          </Navbar.Collapse>
        </Container>
      </Navbar>
      {registrationToggle ? (
        <Container className="d-flex mt-5 justify-content-center vh-100">
          <Form onSubmit={e => submitRegistration(e)}>
            <InputGroup className="mb-3" size="lg">
              <InputGroup.Text id="username">
                <Person />
              </InputGroup.Text>
              <Form.Control
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
              />
            </InputGroup>
            <InputGroup className="mb-3" size="lg">
              <InputGroup.Text id="password">
                <Key />
              </InputGroup.Text>
              <Form.Control
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </InputGroup>
            <InputGroup className="mb-3" size="lg">
              <InputGroup.Text id="password-confirm">
                <Key />
              </InputGroup.Text>
              <Form.Control
                type="password"
                placeholder="Password confirm"
                value={passwordConfirm}
                onChange={e => setPasswordConfirm(e.target.value)}
              />
            </InputGroup>
            <Button variant="primary" type="submit">
              Submit
            </Button>
          </Form>
        </Container>
      ) : (
        <Container className="d-flex mt-5 justify-content-center vh-100">
          <Form onSubmit={e => submitLogin(e)}>
            <InputGroup className="mb-3" size="lg">
              <InputGroup.Text id="username">
                <Person />
              </InputGroup.Text>
              <Form.Control
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
              />
            </InputGroup>
            <InputGroup className="mb-3" size="lg">
              <InputGroup.Text id="password">
                <Key />
              </InputGroup.Text>
              <Form.Control
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </InputGroup>
            <Button variant="primary" type="submit">
              Submit
            </Button>
          </Form>
        </Container>
      )}
    </>
  );
};

export default Auth;
