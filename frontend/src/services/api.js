import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const chatWithData = async (message) => {
  try {
    const response = await axios.post(`${API_URL}/api/v1/chat`, {
      message
    });
    return response.data;
  } catch (error) {
    console.error('Error querying API:', error);
    throw error;
  }
};
