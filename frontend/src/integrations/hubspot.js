import { useState, useEffect } from 'react';
import { Box, Button, CircularProgress } from '@mui/material';
import axios from 'axios';

export const HubSpotIntegration = ({ user, org, integrationParams, setIntegrationParams }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);

    // Function to open OAuth in a new window
    const handleConnectClick = async () => {
        try {
            setIsConnecting(true);
            
            // Update to use POST request with Form data
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
            
            const response = await axios.post(
                `http://localhost:8000/integrations/hubspot/authorize`, 
                formData
            );
            
            const authURL = response?.data;
            
            // Open authorization in popup
            const newWindow = window.open(authURL, 'HubSpot Authorization', 'width=600, height=600');

            // Polling for the window to close
            const pollTimer = window.setInterval(() => {
                if (newWindow?.closed !== false) { 
                    window.clearInterval(pollTimer);
                    handleWindowClosed();
                }
            }, 200);
        } catch (e) {
            setIsConnecting(false);
            alert(e?.response?.data?.detail || 'Authorization failed');
        }
    };

    // Function to handle logic when the OAuth window closes
    const handleWindowClosed = async () => {
        try {
            // Update to use POST request with Form data
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
            
            const response = await axios.post(
                `http://localhost:8000/integrations/hubspot/credentials`, 
                formData
            );
            
            const credentials = response.data;
            if (credentials) {
                setIsConnected(true);
                setIntegrationParams(prev => ({ ...prev, credentials: credentials, type: 'HubSpot' }));
            }
            setIsConnecting(false);
        } catch (e) {
            setIsConnecting(false);
            alert(e?.response?.data?.detail || 'Failed to retrieve credentials');
        }
    };

    // Function to load HubSpot data
    const loadHubSpotData = async () => {
        try {
            if (!integrationParams?.credentials) return;
            
            const formData = new FormData();
            formData.append('credentials', integrationParams.credentials);
            
            const response = await axios.post(
                `http://localhost:8000/integrations/hubspot/load`, 
                formData
            );
            
            // Process the response as needed
            console.log('HubSpot data:', response.data);
        } catch (e) {
            console.error('Error loading HubSpot data:', e);
        }
    };

    useEffect(() => {
        setIsConnected(!!integrationParams?.credentials);
        
        // Load data when credentials are available
        if (integrationParams?.credentials && integrationParams?.type === 'HubSpot') {
            loadHubSpotData();
        }
    }, [integrationParams]);

    return (
        <Box sx={{ mt: 2 }}>
            <Box display='flex' alignItems='center' justifyContent='center' sx={{ mt: 2 }}>
                <Button 
                    variant='contained' 
                    onClick={isConnected ? () => {} : handleConnectClick}
                    color={isConnected ? 'success' : 'primary'}
                    disabled={isConnecting}
                    style={{
                        pointerEvents: isConnected ? 'none' : 'auto',
                        cursor: isConnected ? 'default' : 'pointer',
                        opacity: isConnected ? 1 : undefined
                    }}
                >
                    {isConnected ? 'HubSpot Connected' : isConnecting ? <CircularProgress size={20} /> : 'Connect to HubSpot'}
                </Button>
            </Box>
        </Box>
    );
}