import React, { useEffect, useState } from 'react';
import { Calendar, Clock } from 'react-bootstrap-icons';

const DateTime = () => {
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');

  useEffect(() => {
    const iid = setInterval(() => {
      const now = new Date();
      const formattedDate = now.toLocaleDateString([], {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
      const formattedTime = now.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
      setDate(`${formattedDate}`);
      setTime(`${formattedTime}`);
    }, 1000);

    return () => {
      clearInterval(iid);
    };
  }, []);

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <Calendar />
      <span style={{ marginLeft: '8px' }}>{date}</span>
      <Clock style={{ marginLeft: '20px' }} />{' '}
      <span style={{ marginLeft: '8px' }}>{time}</span>
    </div>
  );
};

export default DateTime;
