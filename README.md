# Message Automation for the smoking study
This project automates parts of generating hundreds of text messages (SMS) sent
to smoking study participants, receiving messages responding to interventions,
and deleting scheduled messages that are not needed any more.

## Commands
### Validate ID
Verifies that the participant ID is in the form `ASHnnn` where n is a number.
Looks up Participant ID in RedCap and indicates which sessions were found there. 

### Generate DD1
Generate events for the first round of daily diary messages.
Use this endpoint after Session 0, preferable the day after, but before Session 1.
If successful, a success message is displayed.
Generating these messages takes only a few seconds.

### Generate value task input
Gets the input files for the values affirmation task for a given participant.
This command goes to REDcap, gets the participant's most-highly rated value
and least-highly rated value, and creates input files based on those values.
If successful, the input files for the value
affirmation task will be available to download.

### Generate intervention SMS and DD2
Generate the text messages for a given participant, including intervention messages, 
messages about daily cigarette usage, messages for boosters, and daily diary round2.
Generating messages takes about 4 minutes because of apptoto's burst rate limits.
If successful, a .csv file with all the messages to be sent to this
participant will be available to download.

### Generate DD3
Generate events for the third round of daily diary messages.
Generating these messages takes only a few seconds.

### Get participant responses
This endpoint returns all the text message responses from the participant, and
the time they responded. These messages will be available for download in a file
named ASHxxx_sms_conversations.csv

### Delete messages
Delete messages scheduled to be sent, for a given participant.
This command deletes messages from the current day, going forward, so
participants who leave the study are not receiving unwanted texts.

### Download files for this subject
Download a zip file containing any .csv files created for this participant.

