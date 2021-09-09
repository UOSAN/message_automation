

def CountResponses(participant_id)

    # Use participant ID to get phone number, then get all events and filter conversations for participant responses.
    rc = Redcap(api_token=current_app.config['AUTOMATIONCONFIG']['redcap_api_token'])

    phone_number = rc.get_participant(participant_id).phone_number

    apptoto = Apptoto(api_token=current_app.config['AUTOMATIONCONFIG']['apptoto_api_token'],
                  user=current_app.config['AUTOMATIONCONFIG']['apptoto_user'])


    return(apptoto.get_conversations(phone_number=phone_number))
