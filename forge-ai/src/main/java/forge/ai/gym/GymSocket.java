package forge.ai.gym;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.ServerSocket;
import java.net.Socket;

/**
 * TCP server wrapper for Gym IPC.
 * Accepts one client, provides newline-delimited JSON messaging.
 */
public class GymSocket implements AutoCloseable {
    private final ServerSocket serverSocket;
    private Socket client;
    private BufferedReader in;
    private PrintWriter out;

    public GymSocket(int port) throws IOException {
        serverSocket = new ServerSocket(port);
        System.out.println("GymSocket listening on port " + port);
    }

    /** Blocks until a client connects. */
    public void acceptClient() throws IOException {
        client = serverSocket.accept();
        in = new BufferedReader(new InputStreamReader(client.getInputStream()));
        out = new PrintWriter(client.getOutputStream(), true);
        System.out.println("GymSocket client connected from " + client.getRemoteSocketAddress());
    }

    /** Send a line of JSON to the client. */
    public void send(String json) {
        out.println(json);
    }

    /** Block until a line of JSON is received from the client. Returns null on EOF. */
    public String receive() throws IOException {
        return in.readLine();
    }

    @Override
    public void close() {
        try { if (in != null) in.close(); } catch (IOException ignored) {}
        try { if (out != null) out.close(); } catch (Exception ignored) {}
        try { if (client != null) client.close(); } catch (IOException ignored) {}
        try { serverSocket.close(); } catch (IOException ignored) {}
    }
}
