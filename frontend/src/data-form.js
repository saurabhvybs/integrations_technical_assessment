import { useState } from 'react';
import {
    Box,
    TextField,
    Button,
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'HubSpot': 'hubspot',
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const endpoint = endpointMapping[integrationType];
    
    const handleLoad = async () => {
        try {
            const formData = new FormData();
            formData.append('credentials', credentials);
            
            const response = await axios.post(
                `http://localhost:8000/integrations/${endpoint}/load`, 
                formData
            );
            
            const { data } = response;
            setLoadedData(JSON.stringify(data, null, 2));
        } catch (e) {
            console.error('Error loading data:', e);
            alert(e?.response?.data?.detail || 'Error loading data');
        }
    };
    
    return (
        <Box sx={{ width: '100%', mt: 2 }}>
            <Box display='flex' justifyContent='center' gap={2}>
                <Button 
                    onClick={handleLoad}
                    variant='contained'
                >
                    Load Data
                </Button>
                <Button 
                    onClick={() => setLoadedData(null)}
                    sx={{mt: 1}}
                    variant='contained'
                >
                    Clear Data
                </Button>
            </Box>
            
            {loadedData && (
                <TextField
                    multiline
                    fullWidth
                    rows={20}
                    value={loadedData}
                    sx={{ mt: 2 }}
                    InputProps={{
                        readOnly: true,
                    }}
                />
            )}
        </Box>
    );
};