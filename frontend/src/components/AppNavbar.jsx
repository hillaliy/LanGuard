import {
  Navbar,
  Nav,
  NavDropdown,
  Container,
  Form,
  InputGroup,
} from 'react-bootstrap';

import DateTime from './DateTime';
import { MoonStars, Search, Sun } from 'react-bootstrap-icons';
import { useContext, useState } from 'react';
import { AppContext } from '../App';
import OffCanvas from './Offcanvas';

function AppNavbar() {
  const { darkMode, setDarkMode, currentUser } = useContext(AppContext);
  const { setCurrentUser, devices, setSearchTerm } = useContext(AppContext);
  const [searchQuery, setSearchQuery] = useState('');

  const toggleDarkMode = () => {
    setDarkMode(prevDarkMode => !prevDarkMode);
  };

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

  const handleSearch = event => {
    event.preventDefault();
    setSearchTerm(filteredDevices);
  };

  const signOut = () => {
    localStorage.removeItem('username');
    localStorage.removeItem('token');
    setCurrentUser('');
  };

  return (
    <Navbar collapseOnSelect expand="lg" className="bg-body-tertiary">
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
        <Navbar.Toggle aria-controls="responsive-navbar-nav" />
        <Navbar.Collapse
          id="responsive-navbar-nav"
          className="justify-content-between"
        >
          <Nav>
            <Form inline onSubmit={handleSearch}>
              <InputGroup>
                <InputGroup.Text id="search">
                  <Search />
                </InputGroup.Text>
                <Form.Control
                  placeholder="Search for devices"
                  aria-label="Search"
                  aria-describedby="search"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </InputGroup>
            </Form>
          </Nav>
          <Nav>
            <DateTime />
          </Nav>
        </Navbar.Collapse>
        <Navbar.Collapse className="justify-content-end">
          <Nav>
            <NavDropdown
              title={
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '32px',
                    height: '32px',
                    backgroundColor: 'black',
                    color: 'white',
                    fontSize: '20px',
                    fontWeight: 'bold',
                    borderRadius: '50%',
                  }}
                >
                  {currentUser &&
                    `${currentUser.username.slice(0, 1).toUpperCase()}`}
                </span>
              }
              id="collapsible-nav-dropdown"
            >
              <NavDropdown.ItemText>
                👤 {currentUser.username}
              </NavDropdown.ItemText>
              <NavDropdown.Divider />
              <NavDropdown.Item href="#action/3.1">
                ✏️ User editing
              </NavDropdown.Item>
              <NavDropdown.Item onClick={signOut}>🔚 Sign out</NavDropdown.Item>
            </NavDropdown>
          </Nav>
          <Nav>
            <Nav.Link
              variant={darkMode ? 'dark' : 'light'}
              onClick={toggleDarkMode}
            >
              {darkMode ? (
                <>
                  <Sun size={20} />
                </>
              ) : (
                <>
                  <MoonStars size={20} />
                </>
              )}
            </Nav.Link>
            <OffCanvas />
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
}

export default AppNavbar;
