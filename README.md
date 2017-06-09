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
Yeah I have a LOT of song and every 3 month a get a lot of new songs to listen (I won't reveal how many Go music ~~).
I listen a lot of Touhou doujin song.

After to sort, create playlist, delete, I want to use as Music alarm or listen music in my house

Aim : Simplify the way to listen music everyday from NAS server and sort/edit song during the listening
To control Multiroom project with 4 types of interface : PC, Web, Android and Voice recognition
Voice recognition will be the priority when I find an easy to use for DEV and easy way to use bluetooth microphone ~~.

Planning :

RPI isn't currently my priority, I have some problem with to receive the audio stream on RPI. I have choppy sound with VLC
and teh problem it's not the power or the speaker but I need to install an package on the RPI but I forget the name and
unfortunately I can't find it. Google my friend doesn't help me ~~.
I hope to create a tag with a with an application with main features before the deadline.

1st Deadline 30/06/2017 : Make everything works as during my student period ie :
Control VLC with socket so I will concentrate on modules :
<ul>
<li>Main objectifs :</li>
<ul>
    <li>Server  : InterfaceSerCli, Service</li>
    <li>Command : VLControl</li>
    <li>Gestion : Music</li>
    <li>Gestion : Create some scripts in bash (I lost all my scripts I need for my project)</li>
    <li>Docs    : Specification and diagrams about my vision of this project</li>
</ul>

<li>Second objectifs :</li>
<ul>
    <li>Command : ManagePlaylist</li>
    <li>RPI     : Get work RPI AUDIO STREAM !</li>
    <li>Docs    : Correct some faults ^^</li>
</ul>
</ul>
2nd Deadline 31/07/2017 : Create a GUI !
I will do and GUI with python for PC, if I have a time to spare I try do a WEB interface I worked on Python-Javascript
Websocket during student project.
<ul>
<li>Main objectifs :</li>
<ul>
    <li>Client  : InterfacePC (temporary name)</li>
    <li>Command : AlarmMusicClock, ManagePlaylist</li>
    <li>RPI     : Get work RPI AUDIO STREAM !</li>
</ul>
<li>Second objectifs :</li>
<ul>
    <li>Client  : InterfaceWeb (temporary name)</li>
    <li>RPI     : InterfaceRPISer, ServiceRPI (Receive audio stream for now)</li>
    <li>Server  : InterfaceSerRPIs, ScanConnectedRPI</li>
    <li>Doc     : PythonDoc</li>
</ul>
</ul>

Third Dealine 30/09/2017 : Make all work !

Main objectifs : Everything not finished.

Second objectifs : Add new functionnalities : Android and vocal interfaces, Interact with youtube

I have some ideas for new features but I need to finish main features, I hope I will respect this deadline.
I will work during my free time because I have a job.

