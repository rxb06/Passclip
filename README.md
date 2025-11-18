
Dependencies: 

```
sudo apt-get install gnupg2 && sudo apt-get install pass
```


1. Generate GPG key
```
	 gpg --full-generate-key: 
```
	Follow prompts, use max security, make a non-expiring key
	
2. Initialise Password store using genrated key ID
```
	pass init <gpg-key-id>
```

3. Adding Password
	 ```
	pass insert bitwarden
	 ```
Also supports multiline using -m



4. Retrieving Passwords
```
	pass bitwarden
```

5. Deleting Passwords
```
pass rm bitwarden
```

6. Generating passwords
```
pass generate bitwarden 18
```

7. Editing Passwords
```
pass edit bitwarden
```


Useful Resource: https://www.passwordstore.org/

Future Improvements and Bug fixes:

1. Add pass tool exception handling for when user is generating pass directly: nter the number of your choice (1): 2
Enter the name for the password entry: Passwords/Test
Enter the desired password length (18): 20
Generating a 20-character password for entry: Passwords/Test
Error generating password: gpg: PassCLI_Archives: skipped: No public key
gpg: : encryption failed: No public key
Password encryption aborted.
2. Error handling for archive function'\s cli escape
3. Enter the name of the archived password to revert: Restore archived password to: (1) Root of password store, (2) Specify a 
subfolder (1): Error reverting archived password '': Usage: pass mv [--force,-f] old-path 
new-path
