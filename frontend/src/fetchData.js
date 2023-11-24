import axios from 'axios';
import { SERVER_URL } from './config';

export async function fetchData(httpMethod, endpoint, id, formData) {
  try {
    const headers = {
      Authorization: `Token ${localStorage.getItem('token')}`,
    };

    if (formData) {
      headers['Content-Type'] = 'multipart/form-data';
    }

    const config = {
      method: httpMethod,
      url: SERVER_URL + endpoint,
      headers: headers,
    };

    if (id && formData) {
      config['params'] = { id: id };
      config['data'] = formData;
    } else if (id) {
      config['params'] = { id: id };
    } else if (formData) {
      config['data'] = formData;
    }

    const response = await axios(config);

    if (response.status >= 200 && response.status < 300) {
      return response.data;
    } else {
      throw new Error(`Request failed with status: ${response.status}`);
    }
  } catch (error) {
    throw new Error(`Request error: ${error.message}`);
  }
}
