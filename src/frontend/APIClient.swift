import Foundation

// MARK: - Response Models

struct GenerateResponse: Codable {
    let candidate: String
    let confidence: Double?
    let model: String?
}

struct HealthResponse: Codable {
    let status: String
}

// MARK: - Error Types

enum APIError: LocalizedError {
    case invalidURL
    case networkError(Error)
    case invalidResponse
    case serverError(statusCode: Int, message: String)
    case decodingError(Error)
    case timeout
    case cancelled

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL configuration"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .invalidResponse:
            return "Invalid response from server"
        case .serverError(let code, let message):
            return "Server error (\(code)): \(message)"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .timeout:
            return "Request timed out"
        case .cancelled:
            return "Request was cancelled"
        }
    }
}

// MARK: - APIClient

/// APIClient communicates with the MindFlow backend using async/await.
/// Supports both single-shot and SSE streaming endpoints.
/// Includes automatic retry on network errors (1 retry).
actor APIClient {

    static let shared = APIClient()

    private var baseURL: String
    private let session: URLSession
    private let maxRetries = 1

    private init() {
        self.baseURL = UserDefaults.standard.string(forKey: "backendURL") ?? "http://localhost:8765"

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 120
        config.waitsForConnectivity = true
        self.session = URLSession(configuration: config)
    }

    // MARK: - Configuration

    func updateBaseURL(_ url: String) {
        self.baseURL = url
    }

    // MARK: - Health Check

    func checkHealth() async -> Bool {
        guard let url = URL(string: "\(baseURL)/health") else { return false }

        do {
            let (_, response) = try await session.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse else { return false }
            return httpResponse.statusCode == 200
        } catch {
            return false
        }
    }

    // MARK: - Generate (Single-shot)

    func generate(text: String, intent: String? = nil) async throws -> GenerateResponse {
        guard let url = URL(string: "\(baseURL)/generate") else {
            throw APIError.invalidURL
        }

        var requestBody: [String: Any] = ["text": text]
        if let intent = intent {
            requestBody["intent"] = intent
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)

        return try await performRequestWithRetry(request: request)
    }

    // MARK: - Generate (SSE Streaming)

    /// Streams the generated response via Server-Sent Events.
    /// Calls `onChunk` for each received text chunk, and returns the full accumulated result.
    func generateStream(text: String, intent: String? = nil, onChunk: @escaping @Sendable (String) -> Void) async throws -> String {
        guard let url = URL(string: "\(baseURL)/generate/stream") else {
            throw APIError.invalidURL
        }

        var requestBody: [String: Any] = ["text": text]
        if let intent = intent {
            requestBody["intent"] = intent
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)

        let (bytes, response) = try await session.bytes(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.serverError(statusCode: httpResponse.statusCode, message: "Stream request failed")
        }

        var accumulated = ""

        for try await line in bytes.lines {
            // SSE format: "data: <content>"
            if line.hasPrefix("data: ") {
                let data = String(line.dropFirst(6))
                if data == "[DONE]" {
                    break
                }
                // Try to parse as JSON chunk
                if let jsonData = data.data(using: .utf8),
                   let chunk = try? JSONDecoder().decode(StreamChunk.self, from: jsonData) {
                    accumulated += chunk.text
                    onChunk(chunk.text)
                } else {
                    // Plain text chunk
                    accumulated += data
                    onChunk(data)
                }
            }
        }

        return accumulated
    }

    // MARK: - Private Helpers

    private func performRequestWithRetry(request: URLRequest) async throws -> GenerateResponse {
        var lastError: Error?

        for attempt in 0...maxRetries {
            do {
                let (data, response) = try await session.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse else {
                    throw APIError.invalidResponse
                }

                guard (200...299).contains(httpResponse.statusCode) else {
                    let body = String(data: data, encoding: .utf8) ?? "Unknown error"
                    throw APIError.serverError(statusCode: httpResponse.statusCode, message: body)
                }

                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                let result = try decoder.decode(GenerateResponse.self, from: data)
                return result

            } catch let error as APIError {
                // Don't retry client errors (4xx) or decoding errors
                switch error {
                case .serverError(let code, _) where code >= 400 && code < 500:
                    throw error
                case .decodingError, .invalidURL, .invalidResponse:
                    throw error
                default:
                    lastError = error
                }
            } catch let error as URLError where error.code == .cancelled {
                throw APIError.cancelled
            } catch let error as URLError where error.code == .timedOut {
                throw APIError.timeout
            } catch {
                lastError = error
            }

            // Wait before retry (exponential backoff)
            if attempt < maxRetries {
                let delay = UInt64(pow(2.0, Double(attempt)) * 500_000_000) // 0.5s, 1s, ...
                try? await Task.sleep(nanoseconds: delay)
                print("[APIClient] Retrying request (attempt \(attempt + 1))...")
            }
        }

        throw APIError.networkError(lastError ?? URLError(.unknown))
    }
}

// MARK: - Stream Chunk Model

private struct StreamChunk: Codable {
    let text: String
    let done: Bool?
}
