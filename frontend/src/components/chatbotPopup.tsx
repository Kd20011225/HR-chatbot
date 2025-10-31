

import { useState, ChangeEvent } from "react";
import {
  PaperClipIcon,
  UserIcon,
  ShieldCheckIcon,
  XMarkIcon,
} from "@heroicons/react/24/solid";
import { Button } from "@/components/ui/button";

interface Message {
  text: string;
  sender: "user" | "bot";
}

export default function ChatbotPopup() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  // Dummy send message function
  const sendMessage = async () => {
    if (!input.trim()) return;
    setLoading(true);
    // Dummy processing
    const result = `Processed: ${input}`;
    const newMessages = [
      ...messages,
      { text: input, sender: "user" as const},
      { text: result, sender: "bot" as const},
    ];
    setMessages(newMessages);
    setInput("");
    setLoading(false);
  };

  // File upload handler (UI only)
  const handleFileUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;
    setMessages((prev) => [
      ...prev,
      { text: `Uploaded: ${selectedFile.name}`, sender: "user" as const},
      { text: "File processing removed.", sender: "bot" as const},
    ]);
  };

  // Dummy info actions
  const showPersonalInfo = () => {
    setMessages((prev) => [
      ...prev,
      { text: "Showing personal information (placeholder).", sender: "bot" as const},
    ]);
  };

  const showPolicy = () => {
    setMessages((prev) => [
      ...prev,
      { text: "Showing policy information (placeholder).", sender: "bot" as const},
    ]);
  };

  // New chat and search chat functions
  const handleNewChat = () => {
    setMessages([]);
  };

  const handleSearchChat = () => {
    alert("Search Chat functionality not implemented.");
  };

  return (
    <>
      {/* Button to open the chat popup */}
      {!isOpen && (
        <button
          className="fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-full shadow-lg"
          onClick={() => setIsOpen(true)}
        >
          Chat
        </button>
      )}

      {/* Chat popup window */}
      {isOpen && (
        <div className="fixed bottom-4 right-4 w-80 h-96 bg-black text-white border border-gray-800 rounded-lg shadow-lg flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-2 border-b border-gray-800">
            <span className="font-bold">Chatbot</span>
            <button onClick={() => setIsOpen(false)}>
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-2 bg-gray-900">
            {messages.length === 0 ? (
              <p className="text-sm text-gray-400">No messages yet.</p>
            ) : (
              messages.map((msg, index) => (
                <div
                  key={index}
                  className={`mb-2 flex ${
                    msg.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`px-2 py-1 rounded ${
                      msg.sender === "user" ? "bg-blue-600" : "bg-gray-700"
                    }`}
                  >
                    {msg.text}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Bottom Bar */}
          <div className="p-2 border-t border-gray-800">
            {/* Upper row: Buttons */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex gap-1">
                <Button
                  onClick={showPersonalInfo}
                  className="flex items-center gap-1 bg-green-600 text-white px-2 py-1"
                >
                  <UserIcon className="w-4 h-4" /> Info
                </Button>
                <Button
                  onClick={showPolicy}
                  className="flex items-center gap-1 bg-yellow-500 text-white px-2 py-1"
                >
                  <ShieldCheckIcon className="w-4 h-4" /> Policy
                </Button>
                <label className="flex items-center bg-gray-700 text-white px-2 py-1 rounded cursor-pointer">
                  <PaperClipIcon className="w-4 h-4" /> Upload
                  <input type="file" className="hidden" onChange={handleFileUpload} />
                </label>
              </div>
              <div className="flex gap-1">
                <Button
                  onClick={handleNewChat}
                  className="bg-blue-600 text-white px-2 py-1"
                >
                  New Chat
                </Button>
                <Button
                  onClick={handleSearchChat}
                  className="bg-gray-600 text-white px-2 py-1"
                >
                  Search Chat
                </Button>
              </div>
            </div>

            {/* Lower row: Input and Send */}
            <div className="flex">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                placeholder="Type a message..."
                className="flex-1 px-2 py-1 rounded bg-gray-800 text-white outline-none"
              />
              <button
                onClick={sendMessage}
                disabled={loading}
                className="bg-blue-600 text-white px-2 py-1 rounded ml-1"
              >
                {loading ? "..." : "Send"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}