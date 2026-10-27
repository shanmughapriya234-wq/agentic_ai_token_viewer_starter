# AI use log

Every prompt to a coding agent or a chatbot about this project goes here. Asking for explanations, pointers to documentation or a hint is allowed; letting an agent write the solution is not.

- Log each prompt when you send it, as one row: the date, the tool or model, the prompt as written, and what you took from the answer.
- A short prompt goes into the table as written. For a long prompt, or one with a line break or a `|`, write "see P1" (P2, P3, ...) in the prompt column and paste the prompt word for word under [Long prompts](#long-prompts).
- Never paste keys, access tokens (such as a Hugging Face token), passwords or personal data. Replace them with `<removed>`.

| Date | Tool or model | Prompt, as written | What we took from the answer |
|---|---|---|---|
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | see P1 | Step 2 was mostly done by the wiring.py change in step 1; what remained: check the page, prove the separate processes, make a wiring.py-only commit, update the README. |
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | [screenshot of VS Code: wiring.py still returning FakeController()] | Our clone did not have step 1 yet; check `git remote -v`, then `git pull`. |
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | https://github.com/shanmughapriya234-wq/agentic_ai_token_viewer_starter.git this the update git check this | Step 1 was on GitHub (commit 6da92be), but wiring.py changed in the same commit as model and controller, so the proof needed its own commit. |
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | [screenshot: git remote -v and the pulled files] | The pull worked; next: uv sync, run the terminal view, start back end and page. |
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | 3. Start the back end. Use the command in README section 1 and leave this terminal running. what ? | The back end is the uvicorn process the page sends commands to; it holds the page's state. |
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | then ? | Start Vite in a second terminal, then Load model and Set messages on the page. |
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | [screenshots of the page: Text alone 8 tokens, chat view 24 tokens] | Bullet 1 of step 2 works; remaining: separate processes and the wiring.py-only proof. |
| 2026-10-26 | Claude Opus 5.5 (claude.ai) | i didnt undertsand tell me clealry what i need to do | Step-by-step: run the terminal view as a separate process, then switch wiring.py to the fake and back, with one commit each. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | [screenshots of VS Code terminals] this is my current vs / this is the new termina; | Which terminal runs what; the terminal view printed 24 and 8 tokens in its own process. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | [screenshot: IndentationError in wiring.py] | Python rejects extra spaces at the start of a line; replaced the whole file. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | [screenshot: Errno 10048 port in use] | An old back end still held port 8000; stopped it with Stop-Process. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | [screenshot of the page with fake data] here where should i find it | The "made-up data" notice is the purple box under the title; the page ran on the fake after a wiring.py change only. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | see P2 | Bullets 1 and 2 were done, bullet 3 needed the two wiring.py commits. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | okay lets continue what should id now / is it fine if its in the backend ? | Commit from backend with the path relative to it. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | [screenshots: second commit, git show --stat, git log] | The proof commit changes only wiring.py. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | [screenshot: Ruff error and push 403] | Ran ruff format and amended the proof commit (now 603acfe); the push needs the repository owner to add me as collaborator. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | https://github.com/shanmughapriya234-wq/agentic_ai_token_viewer_starter do it for me | Only the owner can add collaborators; asked her to invite me. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | like now i cant make her add she ll do it tomorrow tell what else isleft that i need to complete | List of local work: Ruff fix, frontend checks, Yours notes, README, this log, breakpoints. |
| 2026-10-27 | Claude Opus 5.5 (claude.ai) | [screenshots: frontend checks, removed Yours notes, README commit] | All six checks pass; the README sections 1, 2, 4, 5 and 6 were drafted with help and checked by us. |

## Long prompts

Each prompt sits between two lines of four backticks, so code blocks inside the prompt stay intact.

### P1

````text
now this is been done now 2. The page

* The starter's page shows the same tokens through your controller, with the details of a selected token.
* The terminal view and the page are two views on the same model and controller classes. Each runs in its own process, with its own instance.
* The proof of your design: the page, written by someone else, works with your controller after a change to `wiring.py` only, without any change to your model or your controller. this i want to complete what to do with solution
````

### P2

````text
. The page

* The starter's page shows the same tokens through your controller, with the details of a selected token.
* The terminal view and the page are two views on the same model and controller classes. Each runs in its own process, with its own instance.
* The proof of your design: the page, written by someone else, works with your controller after a change to `wiring.py` only, without any change to your model or your controller. are we solving this ?
````
   | 2026-10-27 | Claude Opus 5.5 (claude.ai) | have completed all these ? / now what i ;eft that i need to complete / i want complete my task completely now | Step 2 works; left: this log, README sections 3 and 7, push after the invite. |