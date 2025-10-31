"use client";

import { useEffect, useState } from "react";
import { ShieldCheckIcon, DocumentChartBarIcon, MapPinIcon } from "@heroicons/react/24/solid";
import { Button } from "@/components/ui/button";

interface Message {
  text: string;
  sender: "user" | "bot";
}

interface ChatSession {
  summary: string;
  messages: Message[];
}

interface PlaceCard {
  name: string;
  address: string;
  rating?: number;
  user_ratings_total?: number;
  price_level?: number;
  open_now?: boolean;
  location: { lat: number; lng: number };
  place_id: string;
  maps_url: string;
  photo_url?: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export default function ChatbotUI() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<ChatSession[]>([]);
  const [input, setInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  // Modes: policy (Drive + LlamaIndex), data (CSV agent), places (Google Maps)
  const [activeMode, setActiveMode] = useState<"policy" | "data" | "places">("policy");

  // Places state
  const [places, setPlaces] = useState<PlaceCard[]>([]);
  const [geo, setGeo] = useState<{ lat: number; lng: number } | null>(null);

  // Geolocation only in client (safe in useEffect)
  useEffect(() => {
    if (!geo && typeof window !== "undefined" && "geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setGeo({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => setGeo(null),
        { enableHighAccuracy: true, timeout: 8000 }
      );
    }
  }, [geo]);

  const summarize = (text: string) => (text.length > 50 ? text.substring(0, 50) + "..." : text);

  const sendMessage = async () => {
    if (!input.trim()) return;
    setLoading(true);

    const userMsg: Message = { text: input, sender: "user" };
    const loadingMsg: Message = { text: "Loading...", sender: "bot" };
    setMessages((prev) => [...prev, userMsg, loadingMsg]);

    try {
      if (activeMode === "places") {
        if (!geo) {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              text: "I need your location to search nearby. Please allow location access.",
              sender: "bot",
            };
            return updated;
          });
        } else {
          const body = {
            query: input, // free text like "coffee", "sushi", "pharmacy"
            location: geo,
            radius: 2000,
            open_now: false,
            min_rating: 0,
          };
          const res = await fetch(`${BACKEND_URL}/places-search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          const data = await res.json();

          if (data?.results?.length) {
            setPlaces(data.results as PlaceCard[]);
            const top = data.results
              .slice(0, 3)
              .map((p: PlaceCard) => `${p.name} (${p.rating ?? "?"}⭐) • ${p.address}`)
              .join("\n");
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = { text: `Here are some options:\n${top}`, sender: "bot" };
              return updated;
            });
          } else {
            setPlaces([]);
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = { text: "No results found nearby.", sender: "bot" };
              return updated;
            });
          }
        }
      } else {
        // policy → /ask-question (Drive KB); data → /ask-data (CSV agent)
        const endpoint = activeMode === "policy" ? "/ask-question" : "/ask-data";
        const res = await fetch(`${BACKEND_URL}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: input }),
        });
        const data = await res.json();

        setMessages((prev) => {
          const updated = [...prev];
          if (res.ok && data?.answer) {
            updated[updated.length - 1] = { text: data.answer, sender: "bot" };
          } else {
            const fallback = activeMode === "policy"
              ? "Knowledge base not available yet on the server. Ask your admin to build the index."
              : "Sorry, I couldn’t get an answer.";
            updated[updated.length - 1] = { text: fallback, sender: "bot" };
          }
          return updated;
        });
      }
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { text: "Backend error.", sender: "bot" };
        return updated;
      });
    }

    setInput("");
    setLoading(false);
  };

  const handleNewChat = () => {
    if (messages.length) {
      const first = messages.find((m) => m.sender === "user");
      const summary = first ? summarize(first.text) : "Chat Session";
      setHistory((prev) => [...prev, { summary, messages }]);
    }
    setPlaces([]);
    setMessages([]);
  };

  const handleSearchChat = () => {
    const q = prompt("Search chat history:");
    if (!q) return;
    const found = history.find((sess) =>
      sess.messages.some((m) => m.text.toLowerCase().includes(q.toLowerCase()))
    );
    if (found) setMessages(found.messages);
    else alert("No matching chat.");
  };

  return (
    <div className="flex h-screen bg-black text-white">
      <aside className="w-1/4 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <div className="flex gap-2 mb-2">
            <Button onClick={handleNewChat} className="bg-blue-600">New Chat</Button>
            <Button onClick={handleSearchChat} className="bg-gray-600">Search Chat</Button>
          </div>
          <h2 className="text-lg font-semibold">Chat History</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-2 bg-gray-900">
          {history.map((sess, i) => (
            <div
              key={i}
              className="mb-2 p-2 rounded bg-gray-800 cursor-pointer hover:bg-blue-700"
              onClick={() => setMessages(sess.messages)}
            >
              <p className="text-sm font-medium truncate">{sess.summary}</p>
            </div>
          ))}
        </div>
      </aside>

      <div className="flex flex-col w-3/4">
        <header className="px-4 py-3 border-b border-gray-800 shadow-md flex justify-between items-center">
          <h1 className="text-xl font-bold">Chatbot UI</h1>

          <div className="flex gap-2 flex-wrap items-center">
            <Button
              onClick={() => setActiveMode("policy")}
              className={activeMode === "policy" ? "bg-yellow-600" : "bg-yellow-500"}
              title="Drive-backed HR policy (LlamaIndex)"
            >
              <ShieldCheckIcon className="w-4 h-4 mr-1" /> Policy
            </Button>
            <Button
              onClick={() => setActiveMode("data")}
              className={activeMode === "data" ? "bg-green-700" : "bg-green-600"}
              title="CSV analytics agent"
            >
              <DocumentChartBarIcon className="w-4 h-4 mr-1" /> Data
            </Button>
            <Button
              onClick={() => setActiveMode("places")}
              className={activeMode === "places" ? "bg-purple-700" : "bg-purple-600"}
              title="Nearby places (Google Maps)"
            >
              <MapPinIcon className="w-4 h-4 mr-1" /> Nearby
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {/* Quick chips for Places mode */}
          {activeMode === "places" && (
            <div className="flex gap-2 flex-wrap">
              {["coffee", "breakfast", "lunch", "dinner", "pharmacy", "gym", "hardware store"].map(
                (tag) => (
                  <button
                    key={tag}
                    onClick={() => setInput(tag)}
                    className="text-xs bg-gray-800 px-2 py-1 rounded border border-gray-700"
                  >
                    {tag}
                  </button>
                )
              )}
            </div>
          )}

          {/* Places result gallery */}
          {activeMode === "places" && places.length > 0 && (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
              {places.map((p) => (
                <div key={p.place_id} className="bg-gray-800 rounded-xl overflow-hidden border border-gray-700">
                  {p.photo_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.photo_url} alt={p.name} className="w-full h-40 object-cover" />
                  )}
                  <div className="p-3 space-y-1">
                    <div className="flex justify-between items-start">
                      <h3 className="font-semibold leading-tight">{p.name}</h3>
                      {typeof p.rating === "number" && (
                        <span className="text-sm bg-gray-700 px-2 py-0.5 rounded">{p.rating} ⭐</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-300">{p.address}</p>
                    <p className="text-xs text-gray-400">
                      {p.user_ratings_total ? `${p.user_ratings_total} reviews • ` : ""}
                      {p.open_now === true ? "Open now" : p.open_now === false ? "Closed" : ""}
                    </p>
                    <div className="flex gap-2 pt-2">
                      <a href={p.maps_url} target="_blank" rel="noreferrer">
                        <Button className="bg-blue-600">Open in Maps</Button>
                      </a>
                      <button
                        className="bg-gray-700 px-3 py-2 rounded"
                        onClick={async () => {
                          const res = await fetch(
                            `${BACKEND_URL}/place-details?place_id=${encodeURIComponent(p.place_id)}`
                          );
                          const det = await res.json();
                          const hours = det.opening_hours?.join(" | ") ?? "Hours not provided";
                          alert(
                            `${det.name}\n${det.formatted_address ?? ""}\n${det.phone ?? ""}\n${det.website ?? ""}\n\n${hours}`
                          );
                        }}
                      >
                        Details
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Chat bubbles */}
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-md px-4 py-2 rounded-xl ${msg.sender === "user" ? "bg-blue-600" : "bg-gray-700"}`}>
                {msg.text}
              </div>
            </div>
          ))}
        </main>

        <div className="px-4 py-4 border-t border-gray-800 bg-black">
          <div className="flex gap-2 max-w-3xl mx-auto">
            <input
              className="flex-1 px-4 py-2 rounded bg-gray-800 outline-none"
              placeholder={
                activeMode === "places" ? "Try: coffee, sushi, pharmacy..." : activeMode === "policy" ? "Ask about HR policy..." : "Ask a data question..."
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            />
            <Button onClick={sendMessage} disabled={loading}>
              {loading ? "Sending..." : "Send"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
