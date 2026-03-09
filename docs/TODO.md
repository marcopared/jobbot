# TODO
1. Simplify adoption works
- come up with test cases -> how to build test cases 
for this extension? how does it detect the greenhouse 
site? (maybe also greenhouse api's might have an 
option to apply automatically)
2. Design feature to upload resume to Simplify, test 
case design comes first
3. Think: how to mitigate bot captchas? You are 
assuming that this will work if we run it on a 
server... if it doesn't work then we might have to run 
it only locally (raspberry pi time?? or time to buy 
gaming desktop??) for now if it doesn't work on 
servers then running on macbook is fine

1. Keep `extensions/simplify` as the repo-owned unpacked extension source and verify it still contains `manifest.json` before Simplify bootstrap/apply work.
2. Maintain the persistent Simplify profile session with normal Simplify login when it expires; do not assume Google SSO bootstrap is reliable in the Playwright-launched browser.
3. Re-run the dummy Simplify smoke test after extension/profile changes in both `file://` mode and localhost mode when needed.
4. Continue using only `dry-run ATS smoke test` checks on harmless real ATS pages, and stop before final submission.
5. Evaluate how much CAPTCHA/login friction makes local-only execution the practical deployment model for now.

## Future Features
1. Simplify resume upload
2. Score enhacement: score based on YOE
3. Score enhancement: score based on Jira stories pdf
- Subtask: extract keywords and store somewhere, 
extraction only needs to happen once or every time new 
Jira stories pdf is uploaded
- Subtask: use scoring with extracted keywords
4. Custom resume builder based on application (per 
application) and Jira stories pdf

1. `resume replacement deferred`: add automated Simplify resume replacement/upload only when the current stored Simplify account state workflow is no longer enough.
2. Add automated Simplify profile mutation/update flows after the current MVP.
3. Score enhancement: score based on YOE.
4. Score enhancement: score based on Jira stories PDF.
5. Custom resume builder based on application and Jira stories PDF.