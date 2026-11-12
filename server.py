import asyncio
import json
import logging
import os
import sys
import time

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from aiohttp import web, WSMsgType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QuizServer")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

def load_questions():
    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar perguntas: {e}")
        return []

def save_questions(questions):
    try:
        with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar perguntas: {e}")
        return False

class QuizGame:
    def __init__(self):
        self.state = "LOBBY"  # LOBBY, QUESTION, REVEAL, LEADERBOARD, PODIUM
        self.questions = load_questions()
        self.current_q_index = 0
        self.time_limit = 20
        self.time_left = 20
        self.question_start_time = 0.0
        self.timer_task = None
        
        # Sockets
        self.hosts = set()  # set of WebSocketResponse
        self.players = {}  # player_id -> {"ws": ws, "name": str, "score": int, "streak": int, "last_answer": None, "answered_at": 0, "correct_count": 0}
        self.answers = {}  # player_id -> {"option_index": int, "time_taken": float, "is_correct": bool, "points": int}
        self.word_cloud_entries = []  # list of {"player_id": str, "text": str}
        self.player_word_counts = {}  # player_id -> int (how many words this player sent)

    def reset_game(self, clear_players=False):
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        self.state = "LOBBY"
        self.current_q_index = 0
        self.questions = load_questions()
        self.answers = {}
        self.word_cloud_entries = []
        self.player_word_counts = {}
        if clear_players:
            self.players = {}
        else:
            for p in self.players.values():
                p["score"] = 0
                p["streak"] = 0
                p["last_answer"] = None
                p["answered_at"] = 0
                p["correct_count"] = 0

    def get_public_players(self):
        return [
            {
                "id": pid,
                "name": p["name"],
                "score": p["score"],
                "streak": p["streak"],
                "answered": (pid in self.answers)
            }
            for pid, p in self.players.items()
        ]

    def get_leaderboard(self):
        sorted_players = sorted(
            self.players.items(),
            key=lambda item: item[1]["score"],
            reverse=True
        )
        return [
            {
                "rank": i + 1,
                "id": pid,
                "name": p["name"],
                "score": p["score"],
                "streak": p["streak"]
            }
            for i, (pid, p) in enumerate(sorted_players)
        ]

    def get_answer_distribution(self):
        current_q = self.get_current_question()
        if not current_q:
            return []
        
        # Word Cloud Question
        if current_q.get("type") == "WORDCLOUD":
            freq = {}
            for entry in self.word_cloud_entries:
                word = (entry.get("text") or "").strip()
                if word:
                    key = word.lower()
                    if key not in freq:
                        freq[key] = {"word": word.capitalize(), "count": 0}
                    freq[key]["count"] += 1
            return sorted(freq.values(), key=lambda x: x["count"], reverse=True)

        # Standard Multiple Choice
        counts = [0] * len(current_q.get("options", []))
        for ans in self.answers.values():
            idx = ans.get("option_index")
            if idx is not None and 0 <= idx < len(counts):
                counts[idx] += 1
        return counts

    def get_current_question(self):
        if 0 <= self.current_q_index < len(self.questions):
            return self.questions[self.current_q_index]
        return None

    def get_state_payload(self, for_host=False, player_id=None):
        current_q = self.get_current_question()
        total_questions = len(self.questions)
        
        q_data = None
        if current_q and self.state in ("QUESTION", "REVEAL", "LEADERBOARD"):
            q_type = current_q.get("type", "CHOICE")
            q_data = {
                "index": self.current_q_index,
                "total": total_questions,
                "type": q_type,
                "question": current_q["question"],
                "options": current_q.get("options", []),
                "maxLength": current_q.get("maxLength", 25),
                "timeLimit": self.time_limit,
                "time_left": self.time_left
            }
            # Only reveal correct answer if REVEAL / LEADERBOARD or if host
            if q_type == "CHOICE" and (self.state in ("REVEAL", "LEADERBOARD", "PODIUM") or for_host):
                q_data["correctIndex"] = current_q.get("correctIndex", 0)

        is_wordcloud = (current_q and current_q.get("type") == "WORDCLOUD")
        total_answers = len(self.player_word_counts) if is_wordcloud else len(self.answers)

        payload = {
            "state": self.state,
            "current_q_index": self.current_q_index,
            "total_questions": total_questions,
            "question": q_data,
            "time_left": self.time_left,
            "total_players": len(self.players),
            "answered_count": total_answers,
            "total_words_count": len(self.word_cloud_entries),
            "players": self.get_public_players() if for_host or self.state == "LOBBY" else None,
            "distribution": self.get_answer_distribution(),
            "leaderboard": self.get_leaderboard() if (self.state in ("LEADERBOARD", "PODIUM") or for_host) else None
        }

        if player_id and player_id in self.players:
            p = self.players[player_id]
            words_sent = self.player_word_counts.get(player_id, 0)
            has_ans = (words_sent >= 3) if is_wordcloud else (player_id in self.answers)
            payload["my_info"] = {
                "id": player_id,
                "name": p["name"],
                "score": p["score"],
                "streak": p["streak"],
                "has_answered": has_ans,
                "words_sent": words_sent,
                "max_words": 3,
                "last_result": self.answers.get(player_id) if self.state in ("REVEAL", "LEADERBOARD") else None
            }

        return payload

    async def broadcast_state(self):
        # Broadcast to hosts
        host_payload = json.dumps({"type": "STATE_UPDATE", "data": self.get_state_payload(for_host=True)})
        dead_hosts = set()
        for host_ws in list(self.hosts):
            try:
                await host_ws.send_str(host_payload)
            except Exception:
                dead_hosts.add(host_ws)
        self.hosts -= dead_hosts

        # Broadcast to each player
        for pid, p in list(self.players.items()):
            p_ws = p.get("ws")
            if p_ws and not p_ws.closed:
                try:
                    p_payload = json.dumps({"type": "STATE_UPDATE", "data": self.get_state_payload(for_host=False, player_id=pid)})
                    await p_ws.send_str(p_payload)
                except Exception:
                    pass

    async def start_question(self, index=0):
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()

        self.current_q_index = index
        current_q = self.get_current_question()
        if not current_q:
            self.state = "PODIUM"
            await self.broadcast_state()
            return

        self.state = "QUESTION"
        self.answers = {}
        self.word_cloud_entries = []
        self.player_word_counts = {}
        self.time_limit = current_q.get("timeLimit", 20)
        self.time_left = self.time_limit
        self.question_start_time = time.time()
        
        await self.broadcast_state()
        self.timer_task = asyncio.create_task(self._run_timer())

    async def _run_timer(self):
        try:
            while self.time_left > 0 and self.state == "QUESTION":
                await asyncio.sleep(1)
                self.time_left -= 1
                
                # Check if all players answered (only for CHOICE questions, so Word Cloud allows multiple words)
                current_q = self.get_current_question()
                is_wc = current_q and current_q.get("type") == "WORDCLOUD"
                if not is_wc and len(self.players) > 0 and len(self.answers) >= len(self.players):
                    break

                # Send quick tick to hosts & players
                tick_payload = json.dumps({
                    "type": "TICK",
                    "time_left": self.time_left,
                    "answered_count": len(self.answers),
                    "total_players": len(self.players)
                })
                for h in list(self.hosts):
                    try:
                        await h.send_str(tick_payload)
                    except:
                        pass
                for p in list(self.players.values()):
                    p_ws = p.get("ws")
                    if p_ws and not p_ws.closed:
                        try:
                            await p_ws.send_str(tick_payload)
                        except:
                            pass

            # Timer ended or all answered -> Auto reveal
            if self.state == "QUESTION":
                await self.reveal_answer()
        except asyncio.CancelledError:
            pass

    async def reveal_answer(self):
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        self.state = "REVEAL"
        await self.broadcast_state()

    async def show_leaderboard(self):
        self.state = "LEADERBOARD"
        await self.broadcast_state()

    async def show_podium(self):
        self.state = "PODIUM"
        await self.broadcast_state()

    async def submit_answer(self, player_id, option_index=None, text_answer=None):
        if self.state != "QUESTION":
            return False
        
        current_q = self.get_current_question()
        if not current_q:
            return False

        q_type = current_q.get("type", "CHOICE")
        time_taken = time.time() - self.question_start_time
        time_ratio = max(0.0, (self.time_limit - time_taken) / self.time_limit)
        player = self.players.get(player_id)
        points = 0
        is_correct = False

        if q_type == "WORDCLOUD":
            max_len = current_q.get("maxLength", 25)
            clean_text = (text_answer or "").strip()[:max_len]
            if not clean_text:
                return False
            
            # Check maximum 3 words per participant
            words_sent = self.player_word_counts.get(player_id, 0)
            if words_sent >= 3:
                return False
            
            self.player_word_counts[player_id] = words_sent + 1
            self.word_cloud_entries.append({"player_id": player_id, "text": clean_text})

            points = 250
            is_correct = True
            if player:
                player["score"] += points

            self.answers[player_id] = {
                "text": clean_text,
                "words_sent": self.player_word_counts[player_id],
                "time_taken": round(time_taken, 2),
                "is_correct": is_correct,
                "points": points
            }
        else:
            if player_id in self.answers:
                return False  # Already answered multiple choice
            if option_index is None:
                return False
            is_correct = (option_index == current_q.get("correctIndex", 0))
            if is_correct:
                # Base 1000 + up to 500 by speed
                points = int(1000 + (time_ratio * 500))
                if player:
                    player["streak"] += 1
                    streak_bonus = min(player["streak"] * 50, 250)
                    points += streak_bonus
                    player["score"] += points
                    player["correct_count"] += 1
            else:
                if player:
                    player["streak"] = 0

            self.answers[player_id] = {
                "option_index": option_index,
                "time_taken": round(time_taken, 2),
                "is_correct": is_correct,
                "points": points
            }

        # Send instant notification to host of answered count & distribution
        await self.broadcast_state()
        return True

game = QuizGame()

# HTTP Handlers
async def index_handler(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

async def host_handler(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "host.html"))

async def api_get_questions(request):
    return web.json_response(game.questions)

async def api_save_questions(request):
    try:
        data = await request.json()
        if not isinstance(data, list):
            return web.json_response({"error": "Formato inválido. Esperada lista de perguntas."}, status=400)
        game.questions = data
        save_questions(data)
        await game.broadcast_state()
        return web.json_response({"success": True, "count": len(data)})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    role = None
    player_id = None

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")

                    if msg_type == "HOST_JOIN":
                        role = "HOST"
                        game.hosts.add(ws)
                        await ws.send_str(json.dumps({
                            "type": "STATE_UPDATE",
                            "data": game.get_state_payload(for_host=True)
                        }))

                    elif msg_type == "PLAYER_JOIN":
                        role = "PLAYER"
                        player_id = data.get("id") or str(int(time.time() * 1000))
                        name = (data.get("name") or "Participante").strip()[:25]
                        
                        if player_id in game.players:
                            # Reconnection
                            game.players[player_id]["ws"] = ws
                            game.players[player_id]["name"] = name
                        else:
                            game.players[player_id] = {
                                "ws": ws,
                                "name": name,
                                "score": 0,
                                "streak": 0,
                                "last_answer": None,
                                "answered_at": 0,
                                "correct_count": 0
                            }
                        
                        await ws.send_str(json.dumps({
                            "type": "JOIN_SUCCESS",
                            "player_id": player_id,
                            "name": name,
                            "data": game.get_state_payload(for_host=False, player_id=player_id)
                        }))
                        await game.broadcast_state()

                    elif msg_type == "SUBMIT_ANSWER":
                        if player_id and player_id in game.players:
                            opt = data.get("option_index")
                            txt = data.get("text")
                            await game.submit_answer(player_id, option_index=opt, text_answer=txt)

                    # Host control actions
                    elif role == "HOST":
                        if msg_type == "START_GAME":
                            await game.start_question(0)
                        elif msg_type == "NEXT_QUESTION":
                            await game.start_question(game.current_q_index + 1)
                        elif msg_type == "REVEAL_ANSWER":
                            await game.reveal_answer()
                        elif msg_type == "SHOW_LEADERBOARD":
                            await game.show_leaderboard()
                        elif msg_type == "SHOW_PODIUM":
                            await game.show_podium()
                        elif msg_type == "RESET_GAME":
                            clear_p = data.get("clear_players", False)
                            game.reset_game(clear_players=clear_p)
                            await game.broadcast_state()
                        elif msg_type == "RESTART_TO_QUESTION_1":
                            # Reset scores and answers, immediately start from Question 1
                            for p in game.players.values():
                                p["score"] = 0
                                p["streak"] = 0
                                p["last_answer"] = None
                                p["answered_at"] = 0
                                p["correct_count"] = 0
                            await game.start_question(0)
                        elif msg_type == "CLEAR_PLAYERS":
                            game.reset_game(clear_players=True)
                            await game.broadcast_state()
                        elif msg_type == "KICK_PLAYER":
                            kick_id = data.get("player_id")
                            if kick_id in game.players:
                                k_ws = game.players[kick_id].get("ws")
                                if k_ws and not k_ws.closed:
                                    await k_ws.send_str(json.dumps({"type": "KICKED"}))
                                    await k_ws.close()
                                del game.players[kick_id]
                                if kick_id in game.answers:
                                    del game.answers[kick_id]
                                await game.broadcast_state()

                except json.JSONDecodeError:
                    pass
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")

    finally:
        if role == "HOST":
            game.hosts.discard(ws)
        elif role == "PLAYER" and player_id in game.players:
            # Mark disconnected
            game.players[player_id]["ws"] = None
            await game.broadcast_state()

    return ws

def create_app():
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/play", index_handler)
    app.router.add_get("/host", host_handler)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/api/questions", api_get_questions)
    app.router.add_post("/api/questions", api_save_questions)
    app.router.add_static("/static/", STATIC_DIR)
    return app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8888))
    print("\n==========================================")
    print("QUIZ INTERATIVO INICIADO COM SUCESSO!")
    print(f"Painel do Apresentador: http://localhost:{port}/host")
    print(f"Tela do Participante:  http://localhost:{port}/")
    print("==========================================\n")
    web.run_app(create_app(), host="0.0.0.0", port=port)
