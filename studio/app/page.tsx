import { redirect } from "next/navigation";

// Chat is the main experience — the root always lands there.
export default function Home() {
  redirect("/chat");
}
