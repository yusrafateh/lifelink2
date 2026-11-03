# Viva Preparation - har member ko yeh samajhna zaroori hai

1. **Project kya hai?** Emergency blood donor matching. Request -> automatic matching -> donor accept/decline -> contact reveal.
2. **Cloud ka kya role hai?** App container/PaaS par chalti hai, 24/7 kisi bhi browser se accessible, config environment variables se, /health check.
3. **MVC kahan hai?** Model = `models/` (SQL), View = `templates/` + `static/`, Controller = `controllers/` (REST endpoints). Business rules `services/` mein.
4. **REST API kya hai? Example?** HTTP + JSON. `POST /api/requests` request banata hai, `GET /api/notifications` donor ki list deta hai.
5. **Multithreading kahan aur kyun?** `services/worker.py`. Web request thread request ko PriorityQueue mein daal kar foran 202 deta hai; 3 worker threads background mein matching karte hain. Test: 9 requests 0.07 s mein accept, ~3 s mein match (single thread mein ~9 s).
6. **Har thread ka apna DB connection kyun?** SQLite connection threads ke darmiyan share nahi karna chahiye.
7. **PriorityQueue kyun?** Critical requests normal se pehle serve hoti hain.
8. **Matching rules?** Same city, compatible blood group (matching.py dictionary), available = 1, last donation >= 90 din purani, account active.
9. **Security kya kya hai?** Password hash (salted), signed expiring token, role-based access (403), login rate limit (429), parameterised SQL (SQL injection se bachao), input validation, security headers + CSP, UI mein `textContent` (XSS se bachao), contact sirf accept ke baad.
10. **Database tables?** users, blood_requests, notifications; foreign keys, CHECK constraints, UNIQUE(request_id, donor_id), index.
11. **Alternatives kya the, Flask monolith kyun?** Serverless (AWS Lambda...) aur microservices se compare kiya: monolith sasta, asaan, demo/test mein reliable; layers alag hain isliye baad mein split ho sakta hai.
12. **SQLite kyun, limitation?** Zero setup, ACID. Limitation: single instance; future mein PostgreSQL (RDS) + SQS.
13. **Server restart par kya hota hai?** Pending/matching requests start-up par dobara queue mein daal di jati hain.
14. **Conflicting requirements?** Privacy vs speed, security vs usability, cost vs availability, medical safety vs donors ki tadad.
15. **Limitations?** SMS simulated hai, free tier sleep/ephemeral disk, hospital verification nahi, MFA nahi.
16. **Testing?** 23 automated tests (auth, RBAC, matching, privacy, queue order) + multithreading experiment.
17. **Apna hissa?** Report page 4 par jo likha hai woh clearly bata sakna chahiye.
