package forge.ai;

import java.io.*;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * Bridge class for communication between Java (Forge) and Python (RL agent).
 * This handles the protocol for sending game states and receiving decisions
 * from the Python RL agent via socket communication.
 */
public class RlBridge {
    
    private static final int DEFAULT_PORT = 12345;
    private static final int TIMEOUT_MS = 30000; // 30 second timeout
    
    private Socket socket;
    private BufferedReader reader;
    private PrintWriter writer;
    private boolean connected = false;
    
    // For asynchronous communication
    private BlockingQueue<String> responseQueue;
    
    public RlBridge() {
        this.responseQueue = new LinkedBlockingQueue<>();
    }
    
    /**
     * Connect to the Python RL agent.
     * The Python agent should be running and listening on the specified port.
     */
    public boolean connect(String host, int port) {
        try {
            // Start as server and wait for Python client to connect
            ServerSocket serverSocket = new ServerSocket(port);
            System.out.println("RL Bridge server started on port " + port + ", waiting for Python client...");
            
            socket = serverSocket.accept();
            System.out.println("Python RL client connected!");
            
            reader = new BufferedReader(new InputStreamReader(socket.getInputStream()));
            writer = new PrintWriter(socket.getOutputStream(), true);
            connected = true;
            
            // Start the response reader thread
            startResponseReader();
            
            // Send a hello message to verify connection
            sendMessage("{\"type\": \"hello\", \"message\": \"Forge RL Bridge connected\"}");
            
            return true;
        } catch (IOException e) {
            System.err.println("Failed to start RL server at " + host + ":" + port + " - " + e.getMessage());
            connected = false;
            return false;
        }
    }
    
    /**
     * Connect to localhost with default port
     */
    public boolean connect() {
        return connect("localhost", DEFAULT_PORT);
    }
    
    /**
     * Send a decision request to the Python agent and wait for response
     */
    public PlayerControllerRl.RlDecisionResponse requestDecision(PlayerControllerRl.RlDecisionRequest request) {
        if (!connected) {
            System.err.println("Not connected to RL agent, using fallback");
            return createFallbackResponse(request);
        }
        
        try {
            // Send request as simple JSON (basic implementation)
            String jsonRequest = createJsonRequest(request);
            sendMessage(jsonRequest);
            
            // Wait for response with timeout
            String responseStr = waitForResponse(10000); // 10 second timeout
            
            if (responseStr != null) {
                return parseJsonResponse(responseStr);
            } else {
                System.err.println("Timeout waiting for RL agent response, using fallback");
                return createFallbackResponse(request);
            }
            
        } catch (Exception e) {
            System.err.println("Error communicating with RL agent: " + e.getMessage());
            e.printStackTrace();
            return createFallbackResponse(request);
        }
    }
    
    private String createJsonRequest(PlayerControllerRl.RlDecisionRequest request) {
        // Basic JSON creation without external library
        StringBuilder json = new StringBuilder();
        json.append("{");
        json.append("\"type\": \"decision_request\",");
        json.append("\"request\": {");
        json.append("\"decisionType\": \"").append(request.decisionType).append("\",");
        json.append("\"options\": [");
        for (int i = 0; i < request.options.size(); i++) {
            if (i > 0) json.append(",");
            json.append("\"").append(escapeJson(request.options.get(i))).append("\"");
        }
        json.append("],");
        json.append("\"minChoices\": ").append(request.minChoices).append(",");
        json.append("\"maxChoices\": ").append(request.maxChoices).append(",");
        json.append("\"metadata\": {}");
        json.append("}");
        json.append("}");
        return json.toString();
    }
    
    private String escapeJson(String str) {
        return str.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
    }
    
    private PlayerControllerRl.RlDecisionResponse parseJsonResponse(String responseStr) {
        // Basic JSON parsing - look for chosenIndices array
        PlayerControllerRl.RlDecisionResponse response = new PlayerControllerRl.RlDecisionResponse();
        
        try {
            // Very simple parsing - look for "chosenIndices":[numbers]
            int start = responseStr.indexOf("\"chosenIndices\":");
            if (start >= 0) {
                start = responseStr.indexOf("[", start);
                int end = responseStr.indexOf("]", start);
                if (start >= 0 && end >= 0) {
                    String arrayContent = responseStr.substring(start + 1, end).trim();
                    if (!arrayContent.isEmpty()) {
                        String[] parts = arrayContent.split(",");
                        for (String part : parts) {
                            try {
                                response.chosenIndices.add(Integer.parseInt(part.trim()));
                            } catch (NumberFormatException e) {
                                // Skip invalid numbers
                            }
                        }
                    }
                }
            }
        } catch (Exception e) {
            System.err.println("Error parsing JSON response: " + e.getMessage());
        }
        
        return response;
    }
    
    /**
     * Send a message to the Python agent
     */
    private void sendMessage(String message) throws IOException {
        if (writer != null) {
            System.out.println("Sending to Python: " + message);
            writer.println(message);
            writer.flush();
        }
    }
    
    /**
     * Wait for a response from the Python agent
     */
    private String waitForResponse(long timeoutMs) {
        long startTime = System.currentTimeMillis();
        StringBuilder buffer = new StringBuilder();
        
        while (System.currentTimeMillis() - startTime < timeoutMs) {
            try {
                if (reader != null && reader.ready()) {
                    int ch = reader.read();
                    if (ch != -1) {
                        char c = (char) ch;
                        if (c == '\n') {
                            String line = buffer.toString().trim();
                            if (!line.isEmpty()) {
                                System.out.println("Received from Python: " + line);
                                return line;
                            }
                            buffer.setLength(0); // Clear buffer
                        } else {
                            buffer.append(c);
                        }
                    }
                } else {
                    Thread.sleep(50); // Longer delay when no data is ready
                }
            } catch (IOException | InterruptedException e) {
                System.err.println("Error waiting for response: " + e.getMessage());
                break;
            }
        }
        
        // Check if we have a partial message in buffer
        String remaining = buffer.toString().trim();
        if (!remaining.isEmpty()) {
            System.out.println("Received partial from Python: " + remaining);
            return remaining;
        }
        
        return null; // Timeout
    }
    
    /**
     * Start a background thread to read responses from the Python agent
     */
    private void startResponseReader() {
        Thread readerThread = new Thread(() -> {
            try {
                String line;
                while (connected && (line = reader.readLine()) != null) {
                    responseQueue.offer(line);
                }
            } catch (IOException e) {
                if (connected) {
                    System.err.println("Lost connection to RL agent: " + e.getMessage());
                    connected = false;
                }
            }
        });
        readerThread.setDaemon(true);
        readerThread.start();
    }
    
    /**
     * Create a fallback response when the RL agent is not available
     */
    private PlayerControllerRl.RlDecisionResponse createFallbackResponse(PlayerControllerRl.RlDecisionRequest request) {
        PlayerControllerRl.RlDecisionResponse response = new PlayerControllerRl.RlDecisionResponse();
        
        // Simple fallback logic - choose first option for most decisions
        if (!request.options.isEmpty()) {
            response.chosenIndices.add(0);
            
            // For multi-choice decisions, choose minimum required
            for (int i = 1; i < Math.min(request.minChoices, request.options.size()); i++) {
                response.chosenIndices.add(i);
            }
        }
        
        return response;
    }
    
    /**
     * Disconnect from the Python agent
     */
    public void disconnect() {
        connected = false;
        try {
            if (socket != null && !socket.isClosed()) {
                sendMessage("{\"type\": \"goodbye\", \"message\": \"Forge RL Bridge disconnecting\"}");
                socket.close();
            }
        } catch (IOException e) {
            System.err.println("Error disconnecting from RL agent: " + e.getMessage());
        }
    }
    
    public boolean isConnected() {
        return connected && socket != null && !socket.isClosed();
    }
    
    // Message classes for JSON serialization
    
    public static class RequestMessage {
        public String type;
        public PlayerControllerRl.RlDecisionRequest request;
    }
    
    public static class ResponseMessage {
        public String type;
        public boolean success;
        public String error;
        public PlayerControllerRl.RlDecisionResponse decision;
    }
    
    /**
     * Utility method to start a simple echo server for testing
     * This can be used to test the bridge without a full Python agent
     */
    public static void startEchoServer(int port) {
        new Thread(() -> {
            try (ServerSocket serverSocket = new ServerSocket(port)) {
                System.out.println("Echo server started on port " + port);
                
                while (!Thread.currentThread().isInterrupted()) {
                    try (Socket clientSocket = serverSocket.accept();
                         BufferedReader in = new BufferedReader(new InputStreamReader(clientSocket.getInputStream()));
                         PrintWriter out = new PrintWriter(clientSocket.getOutputStream(), true)) {
                        
                        System.out.println("Client connected to echo server");
                        
                        String inputLine;
                        
                        while ((inputLine = in.readLine()) != null) {
                            System.out.println("Received: " + inputLine);
                            
                            try {
                                // Simple echo server - just respond with success
                                if (inputLine.contains("hello")) {
                                    out.println("{\"type\": \"hello_response\", \"success\": true}");
                                } else if (inputLine.contains("decision_request")) {
                                    // Echo back a simple response - choose first option
                                    out.println("{\"type\": \"decision_response\", \"success\": true, \"decision\": {\"chosenIndices\": [0]}}");
                                }
                            } catch (Exception e) {
                                out.println("{\"type\": \"error\", \"success\": false, \"error\": \"" + e.getMessage() + "\"}");
                            }
                        }
                        
                    } catch (IOException e) {
                        System.err.println("Echo server client error: " + e.getMessage());
                    }
                }
            } catch (IOException e) {
                System.err.println("Echo server error: " + e.getMessage());
            }
        }).start();
    }
    
    // Test main method
    public static void main(String[] args) {
        // Start echo server for testing
        startEchoServer(DEFAULT_PORT);
        
        // Test the bridge
        RlBridge bridge = new RlBridge();
        if (bridge.connect()) {
            System.out.println("Connected to echo server");
            
            // Create a test request
            PlayerControllerRl.RlDecisionRequest testRequest = new PlayerControllerRl.RlDecisionRequest(
                PlayerControllerRl.RlDecisionType.CHOOSE_CARDS_FROM_LIST, 
                null
            );
            testRequest.options.add("Lightning Bolt");
            testRequest.options.add("Counterspell");
            testRequest.options.add("Giant Growth");
            
            PlayerControllerRl.RlDecisionResponse response = bridge.requestDecision(testRequest);
            System.out.println("Received response: " + response.chosenIndices);
            
            bridge.disconnect();
        } else {
            System.out.println("Failed to connect to echo server");
        }
    }
}