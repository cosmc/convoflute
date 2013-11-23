# CONVOFLUTE by Colin McSwiggen
# A little convolution-based intstrument/sound-design tool.
# Released in 2013 under a Creative Commons BY-NC-SA license.

import numpy as np
import numm
import sys

SAMPLE_RATE = 44100  # By default the audio will play back at 44.1kHz.  Changing this constant will frequency shift the output I suppose.
outX = 0  # X coordinate of current position in playback grid.
outY = 0  # Y coordinate of current position in playback grid.
vidWidth = 1440  # Width of video output.
vidHeight = 900  # Height of video output.
fileName1 = "file1.wav"  # Input audio filenames.  Should be given as the second and third command-line arguments.
fileName2 = "file2.wav"
chunkSize = 4096  # The number of samples per chunk.  Should be given as the first command-line argument.
currentSpectrum = np.zeros(chunkSize)  # The current convolution spectrum, for the visualization.


def chunkulate(sound, chunkLength):
	# sound is a 2-channel sound represented as a 2-by-whatever numpy array.
	# chunkLength is the desired chunk length in samples.
	# Returns a floor(whatever/chunkLength)-by-2-by-chunkLength--length numpy array
	# containing the chunks.  Remainder samples at the end of the sound are discarded.
	return np.array( [sound[i*chunkLength:(i+1)*chunkLength] for i in range(sound.shape[0]/chunkLength)] )


def scale(arr, maxVal):
	# Returns arr, a numpy array, scaled to max absolute value maxVal.
	return arr * (maxVal/np.amax(np.absolute(arr)))


def audio_out(chunk):
	global currentSpectrum

	# Locate the appropriate chunks of the input files.
	chunk1 = windowed1[int( outX * windowed1.shape[0] )]
	chunk2 = windowed2[int( outY * windowed2.shape[0] )]

	spectrum = np.fft.rfft(chunk1.T) * np.fft.rfft(chunk2.T)  # Calculate the frequency-domain product of the chunks.
	conv = np.fft.irfft(spectrum).T # Calculate the convolution of the chunks.
	chunk += scale(conv, 32000).astype('int16')  # Output the scaled convolution.
	currentSpectrum = spectrum


def video_out(frame):
	global currentSpectrum
	
	frame[:,:,:] = 0  # Start with a black frame.

	# Visualize the current audio spectrum.
	brights = np.clip(4*np.mean(np.log(np.absolute(currentSpectrum)), axis=0), 0, 255).astype('int16')  # Derive brightness values from the spectrum.
	print brights
	for i in range(frame.shape[1]):  # TODO: Get rid of this for loop.
		frame[:,i,:] = brights[int(i * float(brights.shape[0])/frame.shape[1])]

	# Draw red crosshairs over the current grid location.
	frame[int(outY*frame.shape[0]),:,0] = 255
	frame[:,int(outX*frame.shape[1]),0] = 255


def mouse_in(event_type, px, py, button):
	# On mouse click, update global click coordinate variables.
	global outX, outY
	if (event_type == 'mouse-button-press'):
		outX = px
		outY = py
		print "CLICK!"
		print "outX: " + str(outX) + "  outY: " + str(outY)


def keyboard_in(event_type, key):
	# Quit on Q. Save current output chunk on space. Navigate playback grid with WASD.
	global runner, outX, outY
	print "KEY DOWN: " + key
	if key == ' ':
		outFile = fileName1 + "--" + fileName2 + "--" + str(chunkSize) + "_" + str(outX) + "_" + str(outY) + ".wav"
		numm.np2sound(currentOutChunk, outFile)
		print "Rendered " + outFile
	elif key == 'q':
		runner.quit()
	elif (key == 'a' and outX > 0.01):
		outX -= 0.01
	elif (key == 'd' and outX < 0.99):
		outX += 0.01
	elif (key == 'w' and outY > 0.01):
		outY -= 0.01
	elif (key == 's' and outY < 0.99):
		outY += 0.01
	print "outX: " + str(outX) + "  outY: " + str(outY)


if (__name__ == "__main__"):

	# The three command-line arguments are the audio chunk size (in samples)
	# and the filenames of the two files to analyze.
	chunkSize = int(sys.argv[1])
	fileName1 = sys.argv[2]
	fileName2 = sys.argv[3]

	# Extract the files to sound!
	print "Extracting " + fileName1 + " and " + fileName2 + "..."
	audio1 = numm.sound2np(fileName1)
	audio2 = numm.sound2np(fileName2)

	# Chunkulate the nparrays.
	print "Chunkulating..."
	chunks1 = chunkulate(audio1, chunkSize)
	chunks2 = chunkulate(audio2, chunkSize)
	print "Chunked " + fileName1 + " into " + str(chunks1.shape) + " chunks."
	print "Chunked " + fileName2 + " into " + str(chunks2.shape) + " chunks."

	# Window the chunks.
	print "Windowing the chunks..."
	windowed1 = chunks1 * np.array(  [np.array( [np.hamming(chunkSize),]*2 ).T,] * chunks1.shape[0]  )
	windowed2 = chunks2 * np.array(  [np.array( [np.hamming(chunkSize),]*2 ).T,] * chunks2.shape[0]  )

	# Run the thing!
	runner = numm.Run(audio_out=audio_out, video_out=video_out, mouse_in=mouse_in, keyboard_in=keyboard_in, width=vidWidth, height=vidHeight, fullscreen=True, audio_chunksize=chunkSize, audio_samplerate=SAMPLE_RATE) # The numm object that plays the sound.
	runner.run()