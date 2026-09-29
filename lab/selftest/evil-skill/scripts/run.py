# FIXTURE. Do not run. Exists to trigger the shell-true rule.
import subprocess

subprocess.run("whoami", shell=True)
