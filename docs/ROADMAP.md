# Development milestones

1. **Feasibility baseline:** reproduce the existing client build; run isolated
   crypto/OS probes; preserve upstream history; identify security and API gaps.
2. **Server port:** compile the existing Dropbear server against unchanged ELKS,
   using native sockets and PTYs; audit 16-bit assumptions and memory. No public
   listening service until authentication and randomness are sound.
3. **SSH interoperability:** modern OpenSSH key exchange, host verification,
   public-key login, commands, interactive shell, rekeying and cleanup. Add
   negative packet/authentication tests and regression checks for other services.
4. **Hardware candidate:** arrange PPC and HP 200LX access with the owner;
   measure runtime, memory, failures and recovery. Retain captured evidence.
5. **Companion tools:** SFTP subsystem and small key utility; native generation
   depends on the validated entropy source. Outbound tools are separately scoped.
6. **First viable release candidate:** reproducible binaries, documented CPU/ELKS
   matrix, installation/rollback instructions and honest limitations. Revisit
   inviting ghaerr only at this milestone. No invitation has been sent.

The public fork is authorized. Publication of a secure release still requires
evidence that these criteria are met; the current feasibility milestone is not
a release candidate.
