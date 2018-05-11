# MultiRoom

All modules developed during my student period was pushed, the cleaning will be now, little by little.
Next step is to fill this file for description (Aim, planning, specification, etc...).
Then repair and check each modules was broken during cleaning process and do unittest in same time.
To avoid to do that again manually the next time ><.
I will redo a lot of comments to generate an acceptable python doc ~~.

Some history, you can skip it, if you don't want read :
I start this project when, I wanted to sort my music, I need to listen before to judge a song and create my playlist to
use when I am in public transports. Of course offline ! I kind listen at least 2hours of music per day..
I know some application as Deezer or Spotify may offers better way (I never tried it ^^').
In my case, there are low chance to listen my favorites artists on it, I have more change to listen on youtube..
To do this task take me a lot of time and I don't really enjoy to sort quickly song ~10sec to  judge a song...
Yeah I have a LOT of song and every 3 month, I download a lot of new songs to listen (I won't reveal how many Go music ~~).
I listen a lot of Touhou doujin song.

After to sort, create playlist, delete, I want to use as Music alarm or listen music in my house

Aim : Simplify the way to listen music everyday from NAS server and sort/edit song during the listening
To control Multiroom project with 4 types of interface : PC, Web, Android and Voice recognition
Voice recognition will be the priority when I find an easy to use for DEV and easy way to use bluetooth microphone ~~.

Planning :

RPI isn't currently my priority, I have some problem with to receive the audio stream on RPI. I have choppy sound with VLC
and the problem it's not the power or the speaker but I need to install an package on the RPI but I forget the name and
unfortunately I can't find it. Google my friend doesn't help me ~~.
I hope to create a tag with a with an application with main features.

Control VLC with socket so I will concentrate on modules :
<ul>
<li>Main objectifs :</li>
<ul>
    <li>Server</li>
	<ul>
		<li>InterfaceSerCli 100%</li>
		<li>Service 100% (Need to implement others features)</li>
		<li>Command</li>
		<ul>
			<li>VLControl 75% (Need to test others commands but the main command are OK)</li>
			<li>Arlarm xx% (Need to test)</li>
			<li>ManagePlaylist 50% (need to test)</li>
		</ul> 
	</ul>
	<li>Client</li>
    <ul>
		<li>GUI PC 50% (Need to implement others features)</li>
    </ul> 
    <li>Gestion</li>
    <ul>
		<li>Music 100% (need to test)</li>
		<li>MusicMetadata 0%</li>
    </ul>

    <li>Docs</li>
    <ul>
		<li>Tutorial to use it</li>
		<li>Specification and diagrams about my vision of this project</li>
    </ul>
</ul>
<li>Secondary objectifs :</li>
	<ul>
	    <li>RPI</li>
		<ul>
			<li>Get work RPI AUDIO STREAM !</li>
			<li>InterfaceSerRPIs 100%</li>
			<li>Manage RPI 25%</li>
		</ul>
		<li>Doc : PythonDoc</li>
	</ul>
</ul>

For later: Add new functionnalities : Android and vocal interfaces, Interact with youtube
If I have a time to spare I try do a WEB interface I worked on Python-Javascript with Websocket during student project.

Currently features working :
Command usable :
VLC.start.pathToPlaylist or dir or VLC.start.pathToMusics/Playlist
VLC.next
VLC.prev
VLC.pause 
VLC.play
VLC.random
VLC.kill
InterfacePC work with minimun command 
--Music.update.info (to update name and path of the current song and print it)

There some problems to get info of current song in some cases :
The metadata title of the song have not same name as namefile...
I don't know if I should forget about it... The only way is to check the metadata of all song to find it...

Temporary manual :
Package needed : vlc, python3
Need some configuration to VLC > Preferences > Click on All > Main Interfaces > activate "Web" 
Need to add password Main Interfaces > Lua > Lua by HTTP > password for pwd_vlc, user_vlc is empty by default
Need to add the name of the interface you use to connect local network. May be eth0, lan0, wlan0, or something else, use ifconfig to know it.
Add the two in your var environment in your .bashrc with :
export user_vlc=""
export pwd_vlc="pwd"
export interface="interface"

Case to use :
On 3 Terminals :
1 Launch $python3 Main.py
2 Launch $python3 Client/GUI/ClientPC/Interface.py
2 Launch $python3 Client/GUI/TestCli.py
3 vlc http://IP_Server:19000 --loop

Terminal 3, it will be not needed for future version
vlc http://IP_Server:19000 --loop and later for multi-users vlc http://IP_Server:PortStream --loop 
I need loop to avoid a drop of VLC client when VLC server go to next song...

Input the command to ClientTestCli.py, it's just an simple communication by socket.
