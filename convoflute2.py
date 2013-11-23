# CONVOFLUTE by Colin McSwiggen
# A little convolution-based intstrument/sound-design tool.
# Released in 2013 under a Creative Commons BY-NC-SA license.

import numpy as np
import numm
import sys
import thread

SAMPLE_RATE = 44100  # By default the audio will play back at 44.1kHz.  Changing this constant will frequency shift the output I suppose.
CHUNK_SIZE = 2048  # The number of samples per chunk. This is assumed to be shorter than one pixel's worth of audio.
# TODO: Allow playback buffers shorter than the chunk size.

VID_WIDTH = 640  # Width of video output.
VID_HEIGHT = 480  # Height of video output.
background = np.zeros((VID_HEIGHT, VID_WIDTH, 3)).astype('uint8')  # A blank background to fill with the spectra visualization later.

outTL = (0.0,0.0)  # Fractional coordinates of top left point of playback rectangle.
outBR = (0.01,0.01)  # Fractional coordinates of bottom right point of playback rectangle.
freshOutTL = (0.0,0.0)  # New values for when outTL is refreshed.
freshOutBR = (0.01,0.01)  # New values for when outBR is refreshed.
rectStale = False  # Indicates whether the rectangle needs to be refreshed.

pressXY = (0,0) # Fractional coordinates of most recent mouse press.

fileName1 = "file1.wav"  # Input audio filenames.  Should be given as command-line arguments.
fileName2 = "file2.wav"

loop = np.zeros((CHUNK_SIZE, 2)).astype('int16')  # This array will hold the current playback buffer.
freshLoop = np.zeros((CHUNK_SIZE, 2)).astype('int16')  # This array will hold the next playback buffer.
audio1 = np.zeros((CHUNK_SIZE, 2)).astype('int16')  # This array will hold the samples from the first input file.
audio2 = np.zeros((CHUNK_SIZE, 2)).astype('int16')  # This array will hold the samples from the second input file.
chunkPtr = 0  # The address within the loop buffer of the first sample of the next chunk to output.
loopStale = False  # Indicates whether the audio_out callback should refresh the loop buffer.


def window(sound):
	# sound is a 2-channel sound represented as a whatever-by-2 numpy array.
	# Returns Hamming-windowed sound.
	return sound * np.array( [np.hamming(sound.shape[0]),]*2 ).T


def scale(arr, mv):
	# Returns arr, a numpy array, scaled to max absolute value mv.
	return arr * (mv/np.amax(np.absolute(arr)))


def convolveSegments(buffer1, buffer2, endpts1, endpts2):
	# buffer1 and buffer 2 are sound buffers represented as whatever-by-2 numpy arrays.
	# endpts1 and endpts2 are tuples of fractional start and stop times of segments within each buffer.
	# Returns the convolution of the indicated buffer segments.

	print "Convolving segments " + str((int(endpts1[0]*buffer1.shape[0]), int(endpts1[1]*buffer1.shape[0]))) + " and " + str((int(endpts2[0]*buffer2.shape[0]), int(endpts2[1]*buffer2.shape[0]))) + "."

	# Extract and window the segments.
	seg1 = window(buffer1[int(endpts1[0]*buffer1.shape[0]):int(endpts1[1]*buffer1.shape[0])])
	seg2 = window(buffer2[int(endpts2[0]*buffer2.shape[0]):int(endpts2[1]*buffer2.shape[0])])

	# Match the lengths of the segments by appending zeros to the shorter one.
	# Ensure that the segments have even length.
	if seg1.shape[0] < seg2.shape[0]:
		print "Padding segment 1..."
		seg1 = np.concatenate( (seg1, np.zeros((seg2.shape[0] - seg1.shape[0] + (seg2.shape[0]%2), 2))), axis=0)
		seg2 = np.concatenate( (seg2, np.zeros(((seg2.shape[0]%2),2))), axis=0 )

	elif seg2.shape[0] < seg1.shape[0]:
		print "Padding segment 2..."
		seg2 = np.concatenate( (seg2, np.zeros((seg1.shape[0] - seg2.shape[0] + (seg1.shape[0]%2), 2))), axis=0)
		seg1 = np.concatenate( (seg1, np.zeros(((seg1.shape[0]%2),2))), axis=0 )

	print "Finished padding. Seg1 length: " + str(seg1.shape[0]) + " Seg2 length: " + str(seg2.shape[0]) + " Convolving..."
	spec = np.fft.rfft(seg1.T) * np.fft.rfft(seg2.T)
	print "spec: " + str(spec)
	convolution = np.fft.irfft(spec).T
	print "Convolution: " + str(convolution)
	return convolution  # Return the convolution.


def updateLoop(buffer1, buffer2, endpts1, endpts2):
	global freshLoop, loopStale

	convolution = convolveSegments(buffer1, buffer2, endpts1, endpts2)
	print "Convolution complete.  Filling fresh buffer."
	freshLoop = scale(convolution, 32000).astype('int16')
	loopStale = True
	print "Current buffer flagged as stale."


def audio_out(chunk):
	global loop, freshLoop, loopStale, chunkPtr, CHUNK_SIZE

	if loopStale:
		print "Found stale loop buffer flag. Refreshing buffer."
		loop = freshLoop
		chunkPtr = 0
		loopStale = False
		print "Loop buffer refreshed!  New loop length: " + str(loop.shape[0])

	print "Filling output audio buffer from sample " + str(chunkPtr) + " of " + str(loop.shape[0]) + "."

	# In the case where the next chunk doesn't wrap, output the next CHUNK_SIZE samples.
	if chunkPtr+CHUNK_SIZE < loop.shape[0]:
		chunk += loop[chunkPtr:chunkPtr+CHUNK_SIZE].astype('int16')
		chunkPtr += CHUNK_SIZE
		print "New chunk pointer: " + str(chunkPtr)

	# Otherwise, wrap around.
	else:
		chunk += np.concatenate((loop[chunkPtr:], loop[:CHUNK_SIZE-(loop.shape[0]-chunkPtr)]), axis=0).astype('int16')
		chunkPtr = CHUNK_SIZE - (loop.shape[0]-chunkPtr)
		print "New chunk pointer: " + str(chunkPtr)


def video_out(frame):
	global background, outTL, outBR, freshOutTL, freshOutBR, rectStale

	# Refresh the rectangle coordinates if they're stale.
	if rectStale:
		print "Found stale rectangle flag, refreshing coordinates."
		outTL = freshOutTL
		outBR = freshOutBR
		rectStale = False

	print "Beginning frame refresh."
	frame[:,:,:] = 0  # Start with a black frame.
	preFrame = frame.astype('int64') # Do the work in here to avoid awkward type errors and value wraparounds.
	preFrame += background  # Blit the background.

	# Draw red and blue lines to indicate current playback rectangle.
	preFrame[int(outTL[1]*frame.shape[0]),:,2] = 255
	preFrame[int(outBR[1]*frame.shape[0]),:,2] = 255
	preFrame[:,int(outTL[0]*frame.shape[1]),0] = 255
	preFrame[:,int(outBR[0]*frame.shape[1]),0] = 255

	# Blit magenta over playback rectangle.
	preFrame[ int(outTL[1]*frame.shape[0]):int(outBR[1]*frame.shape[0]), int(outTL[0]*frame.shape[1]):int(outBR[0]*frame.shape[1]) ] += [50,0,50]
	frame += np.clip(preFrame, 0, 255).astype('uint8')
	print "Fresh frame passed."


def mouse_in(event_type, px, py, button):
	# On click and drag, update playback rectangle.
	global freshOutTL, freshOutBR, rectStale, pressXY, freshLoop, loopStale
	if (event_type == 'mouse-button-press'):
		pressXY = (px,py)
		print "MOUSE DOWN!"
		print "px: " + str(px) + "  py: " + str(py)
	if (event_type == 'mouse-button-release'):
		print "MOUSE UP!"
		print "px: " + str(px) + "  py: " + str(py)
		if (px != pressXY[0] and py != pressXY[1]):
			print "Updating coords."
			freshOutTL = (min(px, pressXY[0]), min(py, pressXY[1]))
			freshOutBR = (max(px, pressXY[0]), max(py, pressXY[1]))
			rectStale = True
			
			try:
				thread.start_new_thread(updateLoop, (audio1, audio2, (freshOutTL[0], freshOutBR[0]), (freshOutTL[1], freshOutBR[1]),))
			except:
				print "Unable to start loop update thread."


def keyboard_in(event_type, key):
	# Quit on Q. Save current output chunk on space. Shift playback rectangle with WASD.
	# TODO: Write a helper function to make the WASD cases less repetitive.
	global runner, freshOutTL, freshOutBR, rectStale
	print "KEY DOWN: " + key
	if key == ' ':
		outFile = fileName1 + "--" + fileName2 + "--" + str(chunkSize) + "_" + str(outX) + "_" + str(outY) + ".wav"
		numm.np2sound(currentOutChunk, outFile)
		print "Rendered " + outFile
	elif key == 'q':
		runner.quit()
	elif (key == 'a' and outTL[0] > 0.01):
		freshOutTL = (freshOutTL[0]-0.01,freshOutTL[1])
		freshOutBR = (freshOutBR[0]-0.01,freshOutBR[1])
		rectStale = True
		try:
			thread.start_new_thread(updateLoop, (audio1, audio2, (freshOutTL[0], freshOutBR[0]), (freshOutTL[1], freshOutBR[1]),))
		except:
			print "Unable to start loop update thread."
	elif (key == 'd' and outBR[0] < 0.99):
		freshOutTL = (freshOutTL[0]+0.01,freshOutTL[1])
		freshOutBR = (freshOutBR[0]+0.01,freshOutBR[1])
		rectStale = True
		try:
			thread.start_new_thread(updateLoop, (audio1, audio2, (freshOutTL[0], freshOutBR[0]), (freshOutTL[1], freshOutBR[1]),))
		except:
			print "Unable to start loop update thread."
	elif (key == 'w' and outTL[1] > 0.01):
		freshOutTL = (freshOutTL[0],freshOutTL[1]-0.01)
		freshOutBR = (freshOutBR[0],freshOutBR[1]-0.01)
		rectStale = True
		try:
			thread.start_new_thread(updateLoop, (audio1, audio2, (freshOutTL[0], freshOutBR[0]), (freshOutTL[1], freshOutBR[1]),))
		except:
			print "Unable to start loop update thread."
	elif (key == 's' and outBR[1] < 0.99):
		freshOutTL = (freshOutTL[0],freshOutTL[1]+0.01)
		freshOutBR = (freshOutBR[0],freshOutBR[1]+0.01)
		rectStale = True
		try:
			thread.start_new_thread(updateLoop, (audio1, audio2, (freshOutTL[0], freshOutBR[0]), (freshOutTL[1], freshOutBR[1]),))
		except:
			print "Unable to start loop update thread."
	print "Updated freshOutTL: " + str(freshOutTL) + "  freshOutBR: " + str(freshOutBR)


if (__name__ == "__main__"):

	# The two command-line arguments are the filenames of the files to analyze.
	fileName1 = sys.argv[1]
	fileName2 = sys.argv[2]

	# Extract the files to sound!
	print "Extracting " + fileName1 + " and " + fileName2 + "..."
	audio1 = numm.sound2np(fileName1)
	audio2 = numm.sound2np(fileName2)

	# Generate the background visualization.
	# TODO: Get rid of these for loops.
	# TODO: Clean up the expressions for calculating the spectra.
	print "Generating background visualization..."
	preBackground = background.astype('float64')
	for i in range(background.shape[1]):
		#preBackground[:,i,:] = np.mean(np.log(np.absolute(np.fft.rfft(window(audio1[int(i * float(audio1.shape[0])/background.shape[1]):int((i+1) * float(audio1.shape[0])/background.shape[1])-1]).T))))
		preBackground[:,i,:] = 0.0005*np.mean(np.absolute(audio1[int(i * float(audio1.shape[0])/background.shape[1]):int((i+1) * float(audio1.shape[0])/background.shape[1])-1]))
	for i in range(background.shape[0]):
		#preBackground[i,:,:] += np.mean(np.log(np.absolute(np.fft.rfft(window(audio2[int(i * float(audio2.shape[0])/background.shape[0]):int((i+1) * float(audio2.shape[0])/background.shape[0])-1]).T))))
		preBackground[i,:,:] *= 0.0005*np.mean(np.absolute(audio2[int(i * float(audio2.shape[0])/background.shape[0]):int((i+1) * float(audio2.shape[0])/background.shape[0])-1]))
	background = np.clip(3*preBackground, 0, 255).astype('uint8')

	# Run the thing!
	runner = numm.Run(audio_out=audio_out, video_out=video_out, mouse_in=mouse_in, keyboard_in=keyboard_in, width=VID_WIDTH, height=VID_HEIGHT, fullscreen=False, audio_chunksize=CHUNK_SIZE, audio_samplerate=SAMPLE_RATE) # The numm object that plays the sound.
	runner.run()